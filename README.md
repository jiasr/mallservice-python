# mallservice-python

mall 电商系统**后端 API 服务**：`Flask + Flask-RESTX + SQLAlchemy + MySQL`。

提供用户、商品/分类、订单/优惠、管理员/菜单权限、图片上传等业务接口，监听端口 `8560`，部署采用 Gunicorn + Docker。

## 快速开始

```bash
cd mallservice-python

# 安装依赖
pip install -r requirements.txt

# 修改 etc/mall/mall.conf 中的数据库连接
# 同步数据库表结构
mall-db-sync --config-file etc/mall/mall.conf

# 启动 API 服务
mall-api --config-file etc/mall/mall.conf
```

## 开发规范

- 本仓库是 `aicode` 父仓库的子模块，开发协作规范以 `../doc/开发规范汇总.md`（aicode 父仓库 `doc/` 目录）为**唯一载体**。
- 本目录的 `AGENTS.md`（及 `CLAUDE.md` / `.cursorrules` / `.github/copilot-instructions.md`）为 AI 协作入口，用任何 AI 工具打开本仓库即自动读取并引导至规范汇总。
- 提交信息格式：`<type>: <中文描述>`；提交前在 `e:\aicode` 运行 `check-commit.ps1` 自查。
- 子模块提交推送后，须在父仓库 `aicode` 更新子模块指针（铁律 3）。
