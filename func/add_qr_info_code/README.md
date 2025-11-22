## 更新方法

```bash
gcloud functions deploy add_qr_info_code \
  --runtime python310 \
  --trigger-http \
  --allow-unauthenticated \
  --region asia-northeast1 \
  --entry-point create_product_label  \
  --set-env-vars NOTION_API_KEY=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, GCS_BUCKET=notion-operator-product-labels
```

gcloud functions deploy handle_create_product_label --runtime python312 --gen2 --trigger-http --allow-unauthenticated --region asia-northeast1 --entry-point notion-operator-qr-buckets --set-env-vars NOTION_API_KEY=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, GCS_BUCKET=notion-operator-product-labels 

## 使用方法
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"page_id": "YOUR_PAGE_ID", "data": "https://example.com", "caption": "Webサイトへのリンク"}' \
  https://REGION-PROJECT_ID.cloudfunctions.net/add_qr_code
```

gcloud storage buckets create gs://notion-operator-qr-buckets --location=asia-northeast1
