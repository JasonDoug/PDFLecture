---
description: Deploy the complete Audio Intelligence Suite to GCP and Firebase
---

This workflow deploys the entire stack (Backends and Frontends).

// turbo
1. Deploy Backend Services
   Run the batch deployment script for Cloud Functions:
   `./deploy_services.sh`

2. Copy Backend URLs
   Note the `PDF Processor URL` and `TTS Service URL` from the output.

// turbo
3. Deploy Frontends to Hosting
   Run the hosting deployment script:
   `./deploy_hosting.sh`
   Provide the URLs from step 2 when prompted.

4. Verify Deployment
   Visit your site at https://pdf2audiobook-477309.web.app
