"""统一对象存储后端（基于 boto3 S3 协议）

通过 S3 兼容协议支持所有主流存储厂商：
- MinIO / Ceph / 自建 S3
- 腾讯云 COS
- 阿里云 OSS
- AWS S3
- Cloudflare R2
- 其他 S3 兼容存储

只需配置 Endpoint + AccessKey + SecretKey + Bucket 即可。
"""
import json
from io import BytesIO
from datetime import timedelta

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig
from oslo_log import log as logging

from mall.common.storage.config import get_storage_config

LOG = logging.getLogger(__name__)

# 连接/读取超时（秒）
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 30

_client = None
_config_hash = None


def _build_s3_client(config):
    """根据配置构建 boto3 S3 client

    通过 endpoint_url 字段适配所有 S3 兼容存储。
    """
    boto_config = BotoConfig(
        connect_timeout=_CONNECT_TIMEOUT,
        read_timeout=_READ_TIMEOUT,
        retries={'max_attempts': 2},
        s3={
            'addressing_style': 'path',     # path-style 兼容更多存储
            'signature_version': 's3v4',    # MinIO 要求 Signature V4
        },
    )

    kwargs = dict(
        service_name='s3',
        aws_access_key_id=config.get('access_key', ''),
        aws_secret_access_key=config.get('secret_key', ''),
        region_name=config.get('region', 'us-east-1'),
        config=boto_config,
    )

    endpoint = config.get('endpoint', '').strip()
    if endpoint:
        # 自动补全 http:// 前缀
        if not endpoint.startswith('http://') and not endpoint.startswith('https://'):
            endpoint = 'http://' + endpoint
        kwargs['endpoint_url'] = endpoint
        kwargs['use_ssl'] = endpoint.startswith('https://')

    return boto3.client(**kwargs)


def _ensure_bucket(client, bucket_name):
    """确保 bucket 存在并设置公开读"""
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        code = e.response['Error'].get('Code', '')
        if code in ('404', 'NoSuchBucket'):
            try:
                client.create_bucket(Bucket=bucket_name)
                LOG.info("已创建 bucket: {}".format(bucket_name))
            except ClientError as ce:
                LOG.warning("创建 bucket 失败: {}".format(ce))
                return
        else:
            LOG.warning("检查 bucket 时出错: {}".format(e))
            return

    # 无论 bucket 是否已存在，都设置公开读策略
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::{}/*".format(bucket_name)],
        }],
    }
    try:
        client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        LOG.info("已设置 bucket {} 为公开读权限".format(bucket_name))
    except ClientError as pe:
        LOG.warning("设置公开读策略失败（可忽略）: {}".format(pe))

    # 设置 CORS，允许浏览器直传
    cors_config = {
        "CORSRules": [{
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag", "x-amz-request-id"],
            "MaxAgeSeconds": 3600,
        }],
    }
    try:
        client.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_config)
        LOG.info("已设置 bucket {} 的 CORS 跨域规则".format(bucket_name))
    except ClientError as ce:
        LOG.warning("设置 CORS 失败（可忽略）: {}".format(ce))


def get_client():
    """获取 S3 client（单例，配置变更自动重建）

    Returns:
        tuple: (boto3_s3_client, config_dict)
    """
    global _client, _config_hash

    config = get_storage_config()
    new_hash = str(sorted(config.items()))

    if _client is None or new_hash != _config_hash:
        _client = _build_s3_client(config)
        _config_hash = new_hash
        bucket = config.get('bucket_name', '')
        if bucket:
            _ensure_bucket(_client, bucket)

    return _client, config


def reset_client():
    """重置 client（用于配置变更后强制重建）"""
    global _client, _config_hash
    _client = None
    _config_hash = None


# ==================== 对外接口 ====================

def _get_public_client():
    """获取使用 public_endpoint 的 S3 client

    用于生成预签名 URL 时，签名中包含正确的公网 Host 头。
    如果未配置 public_endpoint，返回默认 client。
    """
    config = get_storage_config()
    public_ep = config.get('public_endpoint', '').strip()
    if not public_ep:
        return get_client()

    pub_config = dict(config)
    pub_config['endpoint'] = public_ep
    pub_client = _build_s3_client(pub_config)
    return pub_client, pub_config


def get_presigned_upload_url(object_name, expires=300):
    """生成预签名上传 URL

    如果配置了 public_endpoint，签名将基于公网地址生成，
    确保浏览器直传时签名验证通过。

    Args:
        object_name: 对象路径（如 images/product/202406/xxx.jpg）
        expires: URL 有效期（秒）

    Returns:
        str: 预签名 PUT URL
    """
    client, config = _get_public_client()
    bucket = config.get('bucket_name', '')
    url = client.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': object_name},
        ExpiresIn=expires,
        HttpMethod='PUT',
    )
    return url


def get_public_url(object_name):
    """获取对象公网访问 URL

    优先使用 public_endpoint，否则用 endpoint 拼接。
    注意：此 URL 不含签名，适用于公开读的 bucket。
    """
    _, config = get_client()
    bucket = config.get('bucket_name', '')
    public_ep = config.get('public_endpoint', '').strip().rstrip('/')

    if public_ep:
        return "{}/{}/{}".format(public_ep, bucket, object_name)

    # 回退：用 endpoint 拼接
    ep = config.get('endpoint', '').strip().rstrip('/')
    if ep:
        if not ep.startswith('http'):
            ep = 'http://' + ep
        return "{}/{}/{}".format(ep, bucket, object_name)

    # 最后的回退：AWS 默认格式
    region = config.get('region', 'us-east-1')
    return "https://{}.s3.{}.amazonaws.com/{}".format(bucket, region, object_name)


def get_relative_url(object_name):
    """获取对象相对路径（不含域名，用于存储到数据库）

    Returns:
        str: 如 /mall-images1/images/product/202606/xxx.jpg
    """
    _, config = get_client()
    bucket = config.get('bucket_name', '')
    return "/{}/{}".format(bucket, object_name)


def get_image_display_url(path):
    """将相对路径转为完整公网 URL（用于 API 返回给前端展示）

    如果 path 已经是完整 URL 则原样返回。
    """
    if not path:
        return path
    if path.startswith('http://') or path.startswith('https://'):
        return path

    _, config = get_client()
    public_ep = config.get('public_endpoint', '').strip().rstrip('/')
    if not public_ep:
        public_ep = config.get('endpoint', '').strip().rstrip('/')
    if not public_ep.startswith('http'):
        public_ep = 'http://' + public_ep
    return "{}{}".format(public_ep, path)


def get_presigned_download_url(object_name, expires=3600):
    """生成预签名下载 URL（带签名的 GET URL）

    用于 bucket 为私有读时，生成带签名的临时访问链接供前端显示图片。
    如果配置了 public_endpoint，签名将基于公网地址生成。

    Args:
        object_name: 对象路径（如 images/product/202406/xxx.jpg）
        expires: URL 有效期（秒），默认 3600

    Returns:
        str: 预签名 GET URL
    """
    client, config = _get_public_client()
    bucket = config.get('bucket_name', '')
    url = client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': object_name},
        ExpiresIn=expires,
        HttpMethod='GET',
    )
    return url


def delete_object(object_name):
    """删除对象"""
    try:
        client, config = get_client()
        client.delete_object(Bucket=config.get('bucket_name', ''), Key=object_name)
        return True
    except (ClientError, BotoCoreError) as e:
        LOG.error("删除文件失败: {}".format(e))
        return False


def upload_file(object_name, file_path_or_data, content_type=None):
    """服务端直接上传文件

    Args:
        object_name: 对象路径
        file_path_or_data: 文件路径(str) 或 二进制数据(bytes)
        content_type: MIME 类型

    Returns:
        str: 公网 URL
    """
    client, config = get_client()
    bucket = config.get('bucket_name', '')

    if isinstance(file_path_or_data, str):
        with open(file_path_or_data, 'rb') as f:
            data = f.read()
    else:
        data = file_path_or_data

    client.put_object(
        Bucket=bucket,
        Key=object_name,
        Body=data,
        ContentType=content_type or 'application/octet-stream',
    )
    return get_public_url(object_name)


def object_exists(object_name):
    """检查对象是否存在"""
    try:
        client, config = get_client()
        client.head_object(Bucket=config.get('bucket_name', ''), Key=object_name)
        return True
    except ClientError:
        return False


def test_connection():
    """测试连接是否正常"""
    try:
        client, _ = get_client()
        client.list_buckets()
        return True
    except (ClientError, BotoCoreError):
        return False
