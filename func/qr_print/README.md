## QR更新方法

```bash
gcloud functions deploy add_qr_code \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --region asia-northeast1 \
  --entry-point add_qr_code \
  --set-env-vars NOTION_API_KEY=
```