# 中文报纸数字档案访问模式

> 2026-07-22 实战：尝试访问 sportslib.chinasportsdaily.cn 2011年报纸版面

## 典型站点特征

中国官方报纸数字档案平台通常：
- **UMI/React SPA**：`#/` 哈希路由，HTML 壳 `<div id="root">`，内容 JS 渲染
- **ASP.NET 后端**：`X-Powered-By: ASP.NET`，IIS 服务器
- **认证墙**：具体版面 URL 返回 404/Bad Request，根页面 200，地址栏跳成 `/undefined`
- **机构订阅制**：高校/体育系统内部 IP 才能访问内容

## 三步访问策略

### 1. 快速判定（1轮，别陷入循环）

```bash
curl -s -o /dev/null -w "%{http_code}" "http://站点/"
curl -s -o /dev/null -w "%{http_code}" "http://站点/具体路径"
```

根 200 + 内容 404 = **认证墙**。立即停止换工具重试——这不是 web_extract vs browser 的问题。

### 2. 全网搜索替代来源

文章**文字内容**可能在别处被引用：
- 高校新闻网（如 news.lcu.edu.cn 转载了本校教师报道）
- 百度百科引用
- CNKI 中国重要报纸全文数据库
- 人民网转载

**关键技巧**：搜文章标题 + 关键人物名 + 报纸名，而非搜报纸版面 URL。

### 3. 如果只要版面图片

报纸扫描图几乎只在官方档案库。认证墙站点：
- 用户能登录 → computer_use 截图保存
- 用户不能登录 → 建议 CNKI、国家图书馆、体育总局档案调取

## 已知站点

| 站点 | 类型 | 认证 |
|------|------|------|
| sportslib.chinasportsdaily.cn | 中国体育报数字档案 | 需登录 |
| paper.people.com.cn | 人民日报图文库 | 部分开放 |
| cnki.net 报纸库 | 知网报纸 | 机构订阅 |

## 反模式：不要反复换工具撞认证墙

web_extract 空 → browser 打不开 → curl 空壳 → agent-reach 搜不到同一URL → **认证问题，非工具问题**。

正确做法：第一步判定后直接告诉用户需要登录，而非用 5+ 种工具逐一重试。
