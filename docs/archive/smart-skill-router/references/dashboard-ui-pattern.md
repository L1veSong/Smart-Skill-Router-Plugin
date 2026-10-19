# Dashboard 配置卡片 UI 模式

> 2026-06-22 实战

## 展示/编辑切换

三种方案实测：

| 方案 | 结果 |
|------|------|
| `display:none` | ✅ 简单可靠，datalist 正确对齐 |
| `opacity + position:absolute` | ❌ datalist 错位，浏览器兼容差 |
| `visibility + absolute` | ❌ 残影，闪跳 |

**最终选择：** `display:none` 简化版。

## HTML 结构

每行 label + 容器(display span + input)：

```html
<div class="card-row">
  <span>Provider</span>
  <span style="position:relative;flex:1;text-align:right">
    <span class="disp">显示值</span>
    <input style="position:absolute;right:0;top:-4px;opacity:0">
  </span>
</div>
```

## JS 切换

```javascript
function edit() {
  // 隐藏 display，显示 input
  document.querySelectorAll(".disp").forEach(e => e.style.opacity = "0");
  document.querySelectorAll("input,select").forEach(e => e.style.opacity = "");
}

function cancel() {
  // 反过来
  document.querySelectorAll("input,select").forEach(e => e.style.opacity = "0");
  document.querySelectorAll(".disp").forEach(e => e.style.opacity = "");
}
```

## Dashboard HTML 修改铁律

1. 改前 `cp backup`
2. 崩了立刻恢复，不在崩盘文件上继续改
3. 只用 patch，不用 execute_code 全量重写
4. 改后检查 brace balance: `sum(1 for c in js if c=='{') - sum(1 for c in js if c=='}')`
5. Cmd+Shift+R 硬刷新 + F12 控制台看报错

## Provider 默认值铁律

所有 provider/model 字段**默认值为空字符串**。不预设任何模型名。
用户配什么用什么，不给错误建议。
