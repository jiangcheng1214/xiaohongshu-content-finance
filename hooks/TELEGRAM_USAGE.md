# Telegram 触发说明

## 触发方式

在 Telegram 中发送以下格式的消息即可触发小红书内容生成：

### 1. 直接话题（默认 finance 垂类）

```
pltr还能追吗
tsla分析
比特币值得买吗
```

### 2. 指定垂类

```
finance: 美联储降息分析
金融: 某新股值得买吗
beauty: 春季口红推荐
美妆: 防晒霜测评
tech: GTC大会总结
科技: 英伟达新显卡评测
```

### 3. 自动识别垂类

- **GTC/英伟达相关** → 自动使用 tech 垂类
- **美妆/口红/护肤相关** → 自动使用 beauty 垂类
- **股票/btc/eth分析** → 自动使用 finance 垂类

## 设置 Telegram 触发

### 方法1: 使用 openclaw 命令（推荐）

```bash
# 将此skill的handler绑定到Telegram
openclaw skill hook --add xiaohongshu-content-generator \
  --channel telegram \
  --pattern ".*" \
  --command "~/.openclaw/skills/xiaohongshu-content-generator/hooks/telegram_handler.sh '{message}' '{chat_id}'"
```

### 方法2: 手动设置

1. 在 Telegram Bot 设置中添加 webhook
2. 指向此脚本的 HTTP 端点
3. 或使用 openclaw 的 message receive 功能轮询

## 快速测试

```bash
# 测试handler（不实际发送到Telegram）
bash ~/.openclaw/skills/xiaohongshu-content-generator/hooks/telegram_handler.sh "pltr还能追吗"

# 查看生成的session
bash ~/.openclaw/skills/xiaohongshu-content-generator/scripts/xhs_generate.sh finance "pltr还能追吗" --info
```

## 输出内容

触发后会自动：
1. 搜索相关配图
2. 生成小红书风格文案
3. 生成封面图
4. 发送到你的Telegram

包含：
- 📸 产品配图 (3张)
- 📱 封面图 (带标题)
- 📝 文案内容
