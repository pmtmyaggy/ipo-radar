# OpenAI 协议兼容平台配置指南

IPO-Radar 支持所有兼容 OpenAI API 协议的大模型平台，包括国内主流平台。

---

## 配置参数说明

```bash
# .env 文件
OPENAI_API_KEY=你的API密钥
OPENAI_BASE_URL=平台API地址
OPENAI_MODEL=模型名称
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | API 密钥 | `sk-xxxxxxxx` 或 `dashscope-xxx` |
| `OPENAI_BASE_URL` | API 基础 URL（关键） | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型 ID | `gpt-4o-mini` / `qwen-turbo` |

---

## 主流平台配置

### 1. OpenAI 官方

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

**获取方式**: https://platform.openai.com/

**费用**: ~$0.001-0.003/次分析

---

### 2. 阿里云百炼 (推荐国内用户)

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx  # 从百炼控制台获取
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-turbo
```

**获取步骤**:
1. 访问 https://dashscope.aliyun.com/
2. 用阿里云账号登录
3. 进入 "API Key 管理" 创建 Key
4. 开通模型服务（有免费额度）

**费用**: 
- qwen-turbo: 免费额度 100万 token
- 超出后约 ¥0.002/千 token

**特点**:
- ✅ 国内访问稳定
- ✅ 中文理解能力强
- ✅ 新用户有免费额度

---

### 3. 智谱 AI (GLM)

```bash
OPENAI_API_KEY=xxxxxxxx.xxxxxxxxxxxxxxxx  # 格式: {id}.{secret}
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-flash
```

**获取步骤**:
1. 访问 https://open.bigmodel.cn/
2. 注册/登录账号
3. 进入 "API Keys" 页面创建

**费用**:
- glm-4-flash: 免费
- glm-4: ¥0.001/千 token

**特点**:
- ✅ 有免费模型 (glm-4-flash)
- ✅ 中文优化好

---

### 4. DeepSeek

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

**获取步骤**:
1. 访问 https://platform.deepseek.com/
2. 注册账号
3. 创建 API Key

**费用**:
- deepseek-chat: ¥0.001-0.002/千 token
- 新用户有 10元 免费额度

**特点**:
- ✅ 推理能力强
- ✅ 价格便宜

---

### 5. 月之暗面 (Moonshot AI / Kimi)

```bash
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_MODEL=moonshot-v1-8k
```

**获取步骤**:
1. 访问 https://platform.moonshot.cn/
2. 注册/登录
3. 创建 API Key

**费用**:
- 新用户有 15元 免费额度
- moonshot-v1-8k: ¥0.006/千 token

**特点**:
- ✅ 长文本支持好
- ✅ 中文能力强

---

### 6. 本地 Ollama（免费，无需联网）

如果你想完全本地化运行：

```bash
# 1. 安装 Ollama
brew install ollama

# 2. 下载轻量级模型
ollama pull llama3.2:1b

# 3. 启动服务
ollama serve

# 4. 配置使用本地模型（不设置 OPENAI_API_KEY）
# 系统会自动检测并使用 Ollama
```

无需配置 `.env`，系统会自动使用本地 Ollama。

---

## 推荐配置（按场景）

### 场景 A: 追求性价比（推荐）
```bash
# 阿里云百炼 - 有免费额度，国内稳定
OPENAI_API_KEY=sk-你的百炼Key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-turbo
```

### 场景 B: 追求准确度
```bash
# OpenAI GPT-4o
OPENAI_API_KEY=sk-你的OpenAIKey
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

### 场景 C: 完全免费
```bash
# 智谱 GLM-4-Flash 或本地 Ollama
OPENAI_API_KEY=你的智谱Key
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-flash
```

### 场景 D: 隐私优先（不上传数据到云端）
```bash
# 本地 Ollama，无需配置 API Key
# 只需安装 Ollama 并运行
```

---

## 验证配置

配置完成后，运行测试：

```bash
cd /Users/zhiyuchen/Downloads/美股爬虫/ipo-radar

python -c "
from src.sentiment.analyzer import LLMClient, SentimentAnalyzer

# 测试 LLM 连接
client = LLMClient()
print(f'LLM 可用: {client.is_available()}')
print(f'使用模型: {client.model}')
print(f'API 地址: {client.base_url}')

# 测试分析
if client.is_available():
    result = client.analyze_sentiment('This IPO shows strong growth potential and market enthusiasm')
    print(f'测试结果: {result}')
"
```

**成功输出**:
```
LLM 可用: True
使用模型: qwen-turbo
API 地址: https://dashscope.aliyuncs.com/compatible-mode/v1
测试结果: {'sentiment': 'bullish', 'score': 0.75, 'reasoning': '文本表达了对IPO的积极看法，提到强劲增长潜力和市场热情'}
```

---

## 故障排查

### 问题 1: 提示 "LLM not available"

**原因**: openai 包未安装或 API Key 未配置

**解决**:
```bash
pip install openai
# 确认 .env 文件中 OPENAI_API_KEY 已设置
```

### 问题 2: 提示连接错误

**原因**: BASE_URL 配置错误

**解决**:
- 检查 URL 是否以 `/v1` 结尾
- 阿里云: `/compatible-mode/v1`
- 智谱: `/api/paas/v4` (不是 `/v1`)

### 问题 3: 提示模型不存在

**原因**: MODEL 名称错误

**解决**:
- 阿里云: `qwen-turbo`, `qwen-plus`, `qwen-max`
- 智谱: `glm-4-flash`, `glm-4`, `glm-4-plus`
- DeepSeek: `deepseek-chat`, `deepseek-coder`

### 问题 4: 余额不足

**解决**: 充值或更换平台。推荐先用有免费额度的平台测试：
- 阿里云百炼（100万 token）
- 智谱 GLM-4-Flash（免费）
- DeepSeek（10元额度）

---

## 费用估算

假设每天分析 50 只股票，每只股票分析 10 条新闻：

| 平台 | 单次费用 | 日费用 | 月费用 |
|------|---------|--------|--------|
| OpenAI gpt-4o-mini | $0.001 | $0.5 | ~$15 |
| 阿里云 qwen-turbo | ¥0.002 | ¥1 | ~¥30 |
| 智谱 glm-4-flash | ¥0 | ¥0 | ¥0 |
| 本地 Ollama | ¥0 | ¥0 | ¥0 |

**结论**: 费用很低，用免费额度完全够用。

---

## 快速配置检查清单

- [ ] 注册平台账号
- [ ] 创建 API Key
- [ ] 确认有可用额度/已充值
- [ ] 编辑 `.env` 填入 `OPENAI_API_KEY`
- [ ] 编辑 `.env` 填入 `OPENAI_BASE_URL`
- [ ] 编辑 `.env` 填入 `OPENAI_MODEL`
- [ ] 运行验证命令确认可用

---

**推荐新手**: 先用 **阿里云百炼** 的 `qwen-turbo`，有免费额度，国内访问稳定。
