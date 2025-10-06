# DPIT Chatbot Integration Examples

This directory contains ready-to-use examples for integrating the DPIT Chatbot into your applications.

## 📁 Directory Structure

```
examples/
├── README.md                          # This file
├── web-component/                     # Web Component implementation
│   ├── chatbot-widget.js             # Reusable Web Component
│   └── demo.html                     # Live demo page
├── iframe-embed/                      # Iframe integration examples
│   └── embed-example.html            # Multiple embed patterns
└── api-clients/                       # API client libraries
    ├── chatbot_client.py             # Python client
    └── chatbot_client.js             # JavaScript/Node.js client
```

## 🚀 Quick Start

### Prerequisites

1. **Start the chatbot server:**
   ```bash
   python app_rag_chat.py
   ```
   The server should be running at `http://127.0.0.1:8000`

2. **Choose your integration method below**

---

## 1️⃣ Web Component (Recommended)

**Best for:** Modern web applications, custom styling, full control

### Files:
- `web-component/chatbot-widget.js` - The Web Component
- `web-component/demo.html` - Live demo

### Usage:

```html
<!DOCTYPE html>
<html>
<head>
  <title>My Website</title>
  <script src="chatbot-widget.js"></script>
</head>
<body>
  <h1>Welcome</h1>
  
  <chatbot-widget 
    api-url="http://127.0.0.1:8000"
    theme="#12a150"
    height="600px"
  ></chatbot-widget>
</body>
</html>
```

### Features:
✅ Direct API integration with streaming  
✅ Customizable theme colors  
✅ Adjustable height  
✅ Auto-resize textarea  
✅ Error handling  
✅ No framework dependencies  

### To Test:
```bash
# Open the demo in your browser
cd examples/web-component
# Then open demo.html in your browser
```

---

## 2️⃣ Iframe Embed

**Best for:** Quick integration, existing websites, minimal setup

### Files:
- `iframe-embed/embed-example.html` - Multiple embed patterns

### Usage:

```html
<!-- Simple embed -->
<iframe 
  src="http://127.0.0.1:8000/chat"
  width="100%"
  height="600px"
  style="border: 1px solid #e5e7eb; border-radius: 8px;"
  allow="microphone"
></iframe>
```

### Patterns Included:
- Standard embed
- Responsive container
- Sidebar layout
- Modal/popup
- Full-width embed

### To Test:
```bash
# Open the examples in your browser
cd examples/iframe-embed
# Then open embed-example.html in your browser
```

---

## 3️⃣ Python API Client

**Best for:** Backend integration, Python applications, automation

### Files:
- `api-clients/chatbot_client.py` - Python client library

### Usage:

```python
from chatbot_client import ChatbotClient

# Create client
client = ChatbotClient()

# Non-streaming request
result = client.ask("List companies in Pune")
print(result['answer'])

# Streaming request
for token in client.ask_stream("Companies with ISO 9001"):
    print(token, end="", flush=True)
```

### Features:
✅ Both streaming and non-streaming modes  
✅ Context manager support  
✅ Health check method  
✅ Full error handling  
✅ Type hints  

### To Test:
```bash
cd examples/api-clients
python chatbot_client.py
```

---

## 4️⃣ JavaScript API Client

**Best for:** Node.js applications, frontend apps without UI, custom integrations

### Files:
- `api-clients/chatbot_client.js` - JavaScript/Node.js client

### Usage (Browser):

```html
<script src="chatbot_client.js"></script>
<script>
  const client = new ChatbotClient();
  
  async function askQuestion() {
    const result = await client.ask("List companies in Bhopal");
    console.log(result.answer);
  }
  
  askQuestion();
</script>
```

### Usage (Node.js):

```javascript
const ChatbotClient = require('./chatbot_client.js');

const client = new ChatbotClient();

// Non-streaming
const result = await client.ask('List companies in Pune');
console.log(result.answer);

// Streaming
for await (const token of client.askStream('Companies with ISO 9001')) {
  process.stdout.write(token);
}
```

### To Test:
```bash
cd examples/api-clients
node chatbot_client.js
```

---

## 📊 Comparison Table

| Feature | Web Component | Iframe | Python Client | JS Client |
|---------|--------------|--------|---------------|-----------|
| **Ease of Setup** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Customization** | ⭐⭐⭐⭐⭐ | ⭐⭐ | N/A | N/A |
| **UI Included** | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Streaming** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Voice Input** | ❌ No | ✅ Yes | ❌ No | ❌ No |
| **Best For** | Modern apps | Quick embed | Backend | Node.js/Browser |

---

## 🎨 Customization Options

### Web Component Attributes:

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `api-url` | string | `http://127.0.0.1:8000` | API endpoint URL |
| `theme` | string | `#12a150` | Primary color (header) |
| `height` | string | `600px` | Widget height |

### Example with all options:
```html
<chatbot-widget 
  api-url="https://your-domain.com/api"
  theme="#3b82f6"
  height="500px"
></chatbot-widget>
```

---

## 🔧 Advanced Configuration

### CORS Setup (for production)

If deploying to a different domain, add CORS to your Flask app:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/ask*": {
        "origins": ["https://yourdomain.com"],
        "methods": ["POST"],
        "allow_headers": ["Content-Type"]
    }
})
```

### Production Deployment

1. **Use HTTPS** - Required for voice features
2. **Configure allowed origins** - Set proper CORS
3. **Add rate limiting** - Prevent abuse
4. **Monitor API usage** - Track requests
5. **Use production WSGI server** - E.g., Waitress, Gunicorn

---

## 🐛 Troubleshooting

### Common Issues:

**Problem:** Cannot connect to API
```
Solution: Make sure the server is running at http://127.0.0.1:8000
Run: python app_rag_chat.py
```

**Problem:** CORS errors
```
Solution: Add CORS headers or use proxy
See Advanced Configuration section above
```

**Problem:** Voice input not working (iframe)
```
Solution: Use HTTPS in production
Voice API requires secure context (except localhost)
```

**Problem:** Streaming not working
```
Solution: Ensure no proxy/buffer is interfering
Check that SSE events are not being buffered
```

**Problem:** Slow responses
```
Solution: 
- Check model loading time
- Adjust k parameter (try lower values)
- Verify semantic search index is built
```

---

## 📚 Additional Resources

- **Main Documentation:** `../CHATBOT_USER_CONTROL_GUIDE.md`
- **API Reference:** See guide for endpoint details
- **Source Code:** `../app_rag_chat.py`
- **Chat Interface:** `../templates/index.html`

---

## 🤝 Support

For questions or issues:
1. Check the troubleshooting section above
2. Review the main documentation guide
3. Examine the example code for patterns
4. Test with the included demo files

---

## 📝 Example Queries to Try

Once you have the chatbot running, try these queries:

```
1. "List companies in Pune"
2. "Companies with ISO 9001 certification"
3. "Show me companies in Maharashtra"
4. "Address of [Company Name]"
5. "How many companies are in Bengaluru?"
6. "Companies with NABL certification"
7. "List products by [Company Name]"
```

---

## 🎯 Next Steps

1. **Start Simple:** Begin with the iframe embed for quick testing
2. **Go Custom:** Move to Web Component for full customization
3. **Backend Integration:** Use Python/JS clients for server-side needs
4. **Production Ready:** Add CORS, HTTPS, rate limiting, monitoring

Happy integrating! 🚀
