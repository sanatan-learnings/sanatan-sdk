# verse-deploy

Deploy Cloudflare Workers as OpenAI API proxy for verse-based projects.

## Synopsis

```bash
verse-deploy
```

## Description

The `verse-deploy` command automates the deployment of Cloudflare Workers that act as an OpenAI API proxy for your verse-based projects. This enables features like spiritual guidance chatbots without exposing your OpenAI API key to users.

For the full lifecycle from initialization to deployment, see `docs/end-to-end-workflow.md`.

**Benefits:**
- **Secure API Key Management**: Keep OpenAI API key server-side
- **Cost Control**: Monitor and limit API usage through Cloudflare
- **Global Edge Network**: Fast response times worldwide
- **Free Tier Available**: Cloudflare Workers offers generous free tier

## Prerequisites

1. **Cloudflare Account** (free): https://dash.cloudflare.com/sign-up
2. **Node.js** installed: https://nodejs.org/
3. **Project files**:
   - `wrangler.toml` - Cloudflare Worker configuration
   - `workers/cloudflare-worker.js` - Worker script
4. **OpenAI API Key**: https://platform.openai.com/api-keys

## How It Works

The deployment script:

1. ✅ Checks Node.js installation
2. ✅ Installs Wrangler CLI (if needed)
3. ✅ Authenticates with Cloudflare
4. ✅ Deploys the worker to Cloudflare's edge network
5. ✅ Configures OpenAI API key as a secret
6. ✅ Tests the worker endpoint
7. ✅ Updates frontend configuration (optional)

## Usage

### Basic Deployment

From your project root directory (where `wrangler.toml` is located):

```bash
verse-deploy
```

The script will interactively guide you through the deployment process.

### What to Expect

```
==========================================
  Cloudflare Worker Deployment
  Hanuman Chalisa
==========================================

✅ Node.js is installed (v20.10.0)
✅ Wrangler CLI is installed (3.20.0)
✅ Already authenticated with Cloudflare
ℹ️  Deploying worker to Cloudflare...

✅ Worker deployed successfully!
✅ Worker URL: https://your-worker.your-subdomain.workers.dev

Would you like to set OPENAI_API_KEY secret now? (y/n):
```

### Setting the OpenAI API Key

During deployment, you'll be prompted to set your OpenAI API key:

```bash
# The script will guide you through:
wrangler secret put OPENAI_API_KEY
# Then paste your OpenAI API key when prompted
```

**Important:** Your API key is stored securely as a Cloudflare secret and never exposed to users.

## Worker Configuration

### wrangler.toml

Your project should have a `wrangler.toml` file:

```toml
name = "hanuman-chalisa-worker"
main = "workers/cloudflare-worker.js"
compatibility_date = "2023-12-01"

[vars]
ALLOWED_ORIGINS = "*"
```

### Worker Script

The worker (`workers/cloudflare-worker.js`) acts as a proxy:

```javascript
// Forwards requests to OpenAI API
// Adds CORS headers
// Uses secret OPENAI_API_KEY from Cloudflare
```

## Frontend Integration

After deployment, update your frontend JavaScript to use the worker:

```javascript
// In assets/js/guidance.js (or your API client)
const WORKER_URL = 'https://your-worker.your-subdomain.workers.dev';

// Use WORKER_URL instead of direct OpenAI API calls
fetch(WORKER_URL, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'gpt-4',
    messages: [{ role: 'user', content: 'Your question' }]
  })
})
```

The deployment script can automatically update `assets/js/guidance.js` if it exists.

## Commands After Deployment

### View Worker Logs

```bash
wrangler tail
```

Real-time logs showing all requests and responses.

### Update OpenAI API Key

```bash
wrangler secret put OPENAI_API_KEY
```

### List Configured Secrets

```bash
wrangler secret list
```

### Redeploy After Changes

```bash
verse-deploy
# or
wrangler deploy
```

### View Metrics

Visit Cloudflare Dashboard: https://dash.cloudflare.com/

- Request count
- Errors
- Response times
- Bandwidth usage

## Testing the Worker

### Manual Test

```bash
curl -X POST https://your-worker.your-subdomain.workers.dev \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 10
  }'
```

Expected response:
```json
{
  "id": "chatcmpl-...",
  "choices": [
    {
      "message": {
        "role": "assistant",
        "content": "Hello!"
      }
    }
  ]
}
```

### Automated Testing

The deployment script automatically tests the worker after deployment.

## Cost & Limits

### Cloudflare Workers (Free Tier)

- ✅ **100,000 requests per day**
- ✅ **10ms CPU time per request**
- ✅ **Global edge network**
- ✅ **Built-in DDoS protection**

For most verse projects, the free tier is sufficient.

### OpenAI API Costs

Worker usage doesn't add costs - you only pay for OpenAI API calls:

- GPT-4: ~$0.03 per 1K tokens
- GPT-3.5: ~$0.002 per 1K tokens

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use Cloudflare secrets** for sensitive data
3. **Set ALLOWED_ORIGINS** to restrict which domains can use your worker
4. **Monitor usage** through Cloudflare dashboard
5. **Set rate limits** if needed (using Cloudflare Rate Limiting)

### Restricting Origins

Update `wrangler.toml`:

```toml
[vars]
ALLOWED_ORIGINS = "https://yourdomain.com,https://www.yourdomain.com"
```

## Troubleshooting

### "wrangler: command not found"

Install Wrangler CLI:
```bash
npm install -g wrangler
```

### "Not logged in to Cloudflare"

Authenticate:
```bash
wrangler login
```

### "Worker test failed"

Check:
1. Is OPENAI_API_KEY set correctly?
   ```bash
   wrangler secret list
   ```
2. Does your OpenAI account have credits?
3. View worker logs:
   ```bash
   wrangler tail
   ```

### "CORS Error" in Browser

The worker script should include CORS headers. Check `workers/cloudflare-worker.js` includes:

```javascript
headers: {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type'
}
```

### "Please run from project root"

Make sure you're in the directory containing `wrangler.toml`:
```bash
cd /path/to/your-project
verse-deploy
```

## GitHub Pages Integration

The deployment script can automatically update your GitHub Pages site to use the worker:

1. Deploys worker to Cloudflare
2. Updates `assets/js/guidance.js` with worker URL
3. Commits and pushes changes
4. GitHub Pages rebuilds automatically (1-2 minutes)

Users can then use features like spiritual guidance without needing their own OpenAI API key!

## Example Projects

- [Hanuman Chalisa](https://github.com/sanatan-learnings/hanuman-chalisa) - Includes spiritual guidance chatbot using Cloudflare Worker

## Workflow

```bash
# 1. Ensure project has required files
ls wrangler.toml workers/cloudflare-worker.js

# 2. Deploy worker
verse-deploy

# 3. Test worker
curl -X POST https://your-worker.workers.dev \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4","messages":[{"role":"user","content":"test"}]}'

# 4. Update frontend to use worker URL

# 5. Push changes to GitHub
git push

# 6. Visit your GitHub Pages site and test the feature
```

## Advanced Configuration

### Custom Domain

Use your own domain instead of `*.workers.dev`:

```bash
wrangler publish --route "api.yourdomain.com/*"
```

### Environment Variables

Add custom variables in `wrangler.toml`:

```toml
[vars]
ALLOWED_ORIGINS = "https://yourdomain.com"
MAX_TOKENS = "1000"
DEFAULT_MODEL = "gpt-4"
```

### Multiple Environments

Deploy to staging and production:

```bash
# Staging
wrangler deploy --env staging

# Production
wrangler deploy --env production
```

## Undeployment

To remove the worker:

```bash
wrangler delete
```

Or through Cloudflare Dashboard: Workers & Pages → Your Worker → Delete

## See Also

- [Cloudflare Workers Docs](https://developers.cloudflare.com/workers/)
- [Wrangler CLI Docs](https://developers.cloudflare.com/workers/wrangler/)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Troubleshooting Guide](../troubleshooting.md)
