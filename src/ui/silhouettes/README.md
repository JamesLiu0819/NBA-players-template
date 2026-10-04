# 球員剪影素材

用途：首頁背景大型浮水印(`body::before`,固定在右下角)跟分享圖
(`downloadShareImage()`,依使用者六軸座標裡最高分的軸挑一張)共用的
籃球員剪影。

## 來源與授權

4 個姿勢,每個都有 `-black`/`-white` 兩個版本(同一張圖只是黑白反相,
方便疊在深色/米白兩種背景上)：

| 檔名 | 姿勢 | 原始素材 |
|---|---|---|
| `dunk-*.png` | 灌籃 | [Slam dunk basketball silhouette](https://freesvg.org/slam-dunk-basketball-silhouette)(freesvg.org,來源 publicdomainvectors.org) |
| `dribble-*.png` | 跑動運球 | [Basketball player outline silhouette](https://freesvg.org/basketball-player-outline-silhouette)(freesvg.org,來源 OpenClipart) |
| `shoot-*.png` | 持球/傳球 | [Basketball player in action vector image](https://freesvg.org/basketball-player-in-action-vector-image)(freesvg.org,來源 OpenClipart) |
| `handle-*.png` | 運球切入 | [Basketball player silhouette clip art](https://freesvg.org/basketball-player-silhouette-clip-art)(freesvg.org,來源 OpenClipart) |

全部是 **Public Domain(CC0)**,可以商用、不需要標註來源——freesvg.org
頁面上寫明「You can copy, modify, distribute and perform the work, even
for commercial purposes, all without asking permission.」。

## 處理方式

原始檔是彩色/單色 PNG,用 `PIL` 把 alpha 通道當剪影遮罩、丟掉原本顏色,
分別填黑色(`#0a0a0a`)跟白色(`#ffffff`)兩版,裁到剪影本身的 bounding
box、統一縮放到高度 420px 存檔(對應的一次性處理腳本沒有留在版本庫裡,
是互動時跑的)。

## 可手動調整的變數

無——這些是裁好的靜態圖檔,不是生成腳本。要調整姿勢對應關係,改
`src/ui/index.html` 裡的 `AXIS_SILHOUETTE`(分享圖用)或 `body::before`
的 `background-image`(首頁浮水印用,目前固定用 `dunk-black.png`)。
