"""对象存储引擎（基于 boto3 S3 协议）

支持：MinIO / Ceph / 腾讯云 COS / 阿里云 OSS / AWS S3 / Cloudflare R2
只需配置 Endpoint + AccessKey + SecretKey + Bucket 即可。
"""
import json
from io import BytesIO

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config as BotoConfig
from oslo_log import log as logging

from mall.db.engines.mysql import get_session
from mall.db.models.StorageConfig.model import StorageConfig

LOG = logging.getLogger(__name__)

# 连接/读取超时（秒）
_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 30

_s3_client = None
_config_hash = None


# ==================== 配置读取 ====================


def get_storage_config():
    """从数据库读取对象存储配置"""
    try:
        session = get_session()
        with session.begin():
            config = session.query(StorageConfig).first()

        if config:
            return {
                "endpoint": config.endpoint or "",
                "access_key": config.access_key or "",
                "secret_key": config.secret_key or "",
                "bucket_name": config.bucket_name or "",
                "region": config.region or "us-east-1",
                "public_endpoint": config.public_endpoint or "",
            }
    except Exception as e:
        LOG.warning("从数据库加载存储配置失败: {}".format(e))

    # 数据库无配置时返回空（首次使用需手动填）
    return {
        "endpoint": "",
        "access_key": "",
        "secret_key": "",
        "bucket_name": "mall-images1",
        "region": "us-east-1",
        "public_endpoint": "",
    }


# ==================== S3 客户端 ====================


def _build_s3_client(config):
    """根据配置构建 boto3 S3 client"""
    boto_config = BotoConfig(
        connect_timeout=_CONNECT_TIMEOUT,
        read_timeout=_READ_TIMEOUT,
        retries={'max_attempts': 2},
        s3={
            'addressing_style': 'path',
            'signature_version': 's3v4',
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
    """获取 S3 client（单例，配置变更自动重建）"""
    global _s3_client, _config_hash

    config = get_storage_config()
    new_hash = str(sorted(config.items()))

    if _s3_client is None or new_hash != _config_hash:
        _s3_client = _build_s3_client(config)
        _config_hash = new_hash
        bucket = config.get('bucket_name', '')
        if bucket:
            _ensure_bucket(_s3_client, bucket)

    return _s3_client, config


def reset_client():
    """重置 S3 client（配置变更后强制重建）"""
    global _s3_client, _config_hash
    _s3_client = None
    _config_hash = None


# ==================== 对外接口 ====================


def _get_public_client():
    """获取使用 public_endpoint 的 S3 client（用于预签名 URL）"""
    config = get_storage_config()
    public_ep = config.get('public_endpoint', '').strip()
    if not public_ep:
        return get_client()

    pub_config = dict(config)
    pub_config['endpoint'] = public_ep
    pub_client = _build_s3_client(pub_config)
    return pub_client, pub_config


def get_presigned_upload_url(object_name, expires=300):
    """生成预签名上传 URL"""
    client, config = _get_public_client()
    bucket = config.get('bucket_name', '')
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': object_name},
        ExpiresIn=expires,
        HttpMethod='PUT',
    )


def get_public_url(object_name):
    """获取对象公网访问 URL"""
    _, config = get_client()
    bucket = config.get('bucket_name', '')
    public_ep = config.get('public_endpoint', '').strip().rstrip('/')

    if public_ep:
        return "{}/{}/{}".format(public_ep, bucket, object_name)

    ep = config.get('endpoint', '').strip().rstrip('/')
    if ep:
        if not ep.startswith('http'):
            ep = 'http://' + ep
        return "{}/{}/{}".format(ep, bucket, object_name)

    region = config.get('region', 'us-east-1')
    return "https://{}.s3.{}.amazonaws.com/{}".format(bucket, region, object_name)


def get_relative_url(object_name):
    """获取对象相对路径（不含域名，用于存储到数据库）"""
    _, config = get_client()
    bucket = config.get('bucket_name', '')
    return "/{}/{}".format(bucket, object_name)


def get_image_display_url(path):
    """将相对路径转为完整公网 URL"""
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
    """生成预签名下载 URL"""
    client, config = _get_public_client()
    bucket = config.get('bucket_name', '')
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': object_name},
        ExpiresIn=expires,
        HttpMethod='GET',
    )


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
    """服务端直接上传文件"""
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


def list_objects(prefix="", delimiter="/", max_keys=1000):
    """列出 bucket 中的对象（模拟文件夹浏览）

    Args:
        prefix: 路径前缀
        delimiter: 分隔符，默认 "/" 实现文件夹分层
        max_keys: 最大返回数

    Returns:
        dict: {
            "files": [{"key": "...", "size": ..., "last_modified": "..."}],
            "folders": ["prefix1/", "prefix2/"],
        }
    """
    try:
        client, config = get_client()
        bucket = config.get('bucket_name', '')
        resp = client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            Delimiter=delimiter,
            MaxKeys=max_keys,
        )

        files = []
        for obj in resp.get('Contents', []):
            if obj['Key'] == prefix:
                continue
            files.append({
                "key": obj['Key'],
                "size": obj['Size'],
                "last_modified": obj['LastModified'].isoformat() if obj.get('LastModified') else '',
            })

        folders = []
        for folder in resp.get('CommonPrefixes', []):
            folders.append(folder['Prefix'])

        return {"files": files, "folders": folders}
    except (ClientError, BotoCoreError) as e:
        LOG.error("列出文件失败: {}".format(e))
        return {"files": [], "folders": []}


def test_connection():
    """用当前已保存的配置测试连接"""
    try:
        client, _ = get_client()
        client.list_buckets()
        return True
    except (ClientError, BotoCoreError):
        return False


def test_connection_with_config(config):
    """用指定参数测试连接（不保存，不修改缓存）

    Args:
        config: dict，包含 endpoint/access_key/secret_key/region
    """
    try:
        client = _build_s3_client(config)
        result = client.list_buckets()
        return True, None
    except Exception as e:
        return False, str(e)
