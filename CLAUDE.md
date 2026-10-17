# prompt-gallery

靜態的 AI 圖像 prompt 畫廊（`index.html` 單檔 + `images/`）。內容規則見 `anthropic-skills:prompt-gallery-curator` skill。

## 簡報／設計：固定套用 HMC Clinical Deck

在任何 session 裡建立 Slides 或 Design artifact（或被要求做投影片、deck、簡報、視覺設計）時：

- **一律使用設計系統「HMC Clinical Deck」**：https://claude.ai/artifact/Wb87b61oBPVHEegXc3jB2e
- 先 `read` 它的 `project/README.md`，照裡面的 tokens、字級下限、配色與反例做；**不要再問要用哪個設計系統**。
- 這個帳號是個人方案，claude.ai 的設計系統清單沒有「設為預設」可按（2026-10-17 確認），所以 quickstart 會回報「沒有預設」——那不是要問使用者，直接套用上面的連結即可。
- 投影片的風格規則、建構步驟與驗收標準 A1–A9 在 `anthropic-skills:slide-hmc-style` skill；Claude Design 交接流程在 `hmcheng0913/llm-wiki` 的 `.claude/slide/`。
