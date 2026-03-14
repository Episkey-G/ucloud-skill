# UCloud Manager Skill

通过自然语言管理 UCloud 云资源，覆盖 40+ 个产品、900+ 个 API。产品目录从远端 GitHub 注册表自动构建，新产品上线即可用。

## 前置准备

### 1. 获取 UCloud API 密钥

登录 [UCloud 控制台](https://console.ucloud.cn) → API 密钥管理，获取 Public Key 和 Private Key。

### 2. 设置环境变量

```bash
export UCLOUD_PUBLIC_KEY="your_public_key"
export UCLOUD_PRIVATE_KEY="your_private_key"

# 可选：设置默认地域和项目，省去每次指定
export UCLOUD_REGION="cn-bj2"
export UCLOUD_PROJECT_ID="org-xxxxxx"
```

建议将以上内容写入 `~/.zshrc` 或 `~/.bashrc`。

### 3. 启动 Claude Code

```bash
claude
```

然后直接用自然语言操作云资源，例如：

- "帮我查一下北京二区域所有 UHost 的运行状态"
- "创建一台 8核16G 的 CentOS 主机，SSD 系统盘 80G，放在上海二"
- "把那台 web-prod-01 从 4核8G 升级到 8核16G"

## 依赖

- Python 3.9+（仅使用标准库，无需 pip install）
- Claude Code CLI
- 网络连接（API参数文档从 GitHub 实时获取）

## 目录结构

```
ucloud-skill/
├── SKILL.md              # Skill 指令（Claude 读取）
├── README.md             # 本文件（人类读取）
├── scripts/              # 运行时脚本
│   ├── route_product.py      # 产品路由 + API 列表 + SOP 提示注入
│   ├── fetch_api_doc.py      # 从 GitHub 获取 API 文档 + 前置依赖提示
│   ├── gen_password.py       # 随机密码生成
│   ├── call_api.py           # API 调用（含签名计算）
│   ├── registry.py           # 远端产品注册表（从 apinav.json 构建）
│   └── cache.py              # 统一 HTTP 缓存模块
├── config/               # 本地配置
│   └── tier1.json            # Tier-1 产品列表
├── hints/                # 业务知识数据（JSON，易维护）
│   ├── product_hints.json    # 产品级 SOP 提示
│   └── api_hints.json        # API 级前置依赖提示
└── references/           # 按需加载的参考文档
```

## 架构特点

- **零本地产品目录维护**：产品注册表从 [UCloudDoc-Team/api](https://github.com/UCloudDoc-Team/api) 的 `apinav.json` 运行时构建，新产品自动可用
- **零本地API数据维护**：参数定义同样从 GitHub 实时获取，始终最新
- **确定性上下文注入**：脚本输出自动包含 `[System Hint]`，消除模型盲猜
- **代码与数据分离**：添加新 hint 只需编辑 `hints/*.json`，无需改 Python

## 维护指南

### 添加/修改 Hint（无需写 Python）

- **新增产品 SOP**：编辑 `hints/product_hints.json`
- **新增 API 前置依赖**：编辑 `hints/api_hints.json`

### 产品目录

产品目录从远端 `apinav.json` 自动构建，无需手动维护。新产品上线后，`route_product.py` 会自动发现。

Tier-1 产品列表在 `config/tier1.json` 中维护（仅影响输出中的 tier1 标记和 SOP 注入）。
