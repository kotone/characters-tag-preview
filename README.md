# Anime Character Tag Database (二次元角色 Tag 中文映射库)

![列表](/images/preview-img-01.png "列表")
![列表](/images/preview-img-02.png "列表")

> [在线地址](https://kotone.github.io/WAI-il-characters-preview/) 图片加载较慢
## 简介 (Introduction)
本项目根据 Danbooru Character Tag 数据，提供中英文映射、作品信息及预览图。主要解决了在使用 AI 绘图工具时,难以将英文 Tag 与角色中文名及其所属作品对应的问题,让创作者能够快速查找和使用正确的角色标签。


### 数据来源与准确性
- **数据源**：角色标签数据自动从 [a1111-sd-webui-tagcomplete](https://github.com/DominikDoom/a1111-sd-webui-tagcomplete) 项目获取，支持缓存和增量更新；
- **中文名**：由 LLM（DeepSeek）辅助生成，准确率较高但可能存在少量幻觉或别名差异；  
- **图片**：通过爬虫从 `Safebooru` 搜索结果中获取第一张图作为预览图。


## ⚠️ 免责声明 (Disclaimer)

1.  **关于图像版权 (Image Copyright)**：
    * **本仓库不托管、不存储、不分发任何图像文件。**
    * 所有预览图均通过“热链接 (Hotlinking)”方式直接引用自原网站 URL。
    * 图像版权完全归原作者或原网站所有。本仓库仅提供 JSON 数据索引和 HTML 预览工具，类似于搜索引擎的功能。
    * 如果原网站对图片链接进行了防盗链设置或删除了原图，本仓库的预览功能可能会失效，作者对此不承担修复义务。

2.  **合规性说明**：
    * 本项目提供的 Python 爬虫脚本严格遵守 Robots 协议（如适用），仅用于技术研究和元数据整理。
    * 用户在使用脚本时，请自行控制请求频率，避免对目标服务器造成压力。

3.  **责任限制**：
    * 任何因使用本仓库数据或代码而导致的法律纠纷（如版权争议、IP 封禁），概与本仓库作者无关。


### 协议 (License)
本项目数据集采用 MIT 协议开源。 所引用的图片版权归原作者及源网站所有。