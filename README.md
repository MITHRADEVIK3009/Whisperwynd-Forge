# Whisperwynd

![Whisperwynd_Illustration](images/Whisperwynd.png)

## Quick Navigation
- [Overview](#overview)
- [Key Features](#key-features)
- [Key Contributions](#key-contributions)
  - [Bot Configuration](#-bot-configuration-botxml)
  - [Application Enhancements](#-application-enhancements-apppy)
  - [Persona Retrieval](#-persona-retrieval-getpersonas-json)
  - [Whisperwynd MCP Server](#-whisperwynd-mcp-server)
- [Installation](#installation)
- [Usage](#usage)
  - [Basic Setup](#basic-setup)
  - [Health Monitoring](#health-monitoring)
  - [MCP Integration](#mcp-integration)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Development](#development)
- [Future Directions](#future-directions)
- [Contributing](#contributing)
- [License](#license)

## Overview

Whisperwynd is an interactive storytelling and persona-driven world-building application. It blends lightweight FastAPI services, Adaptive Cards, and a Model Context Protocol (MCP) server to provide both **human-friendly** and **AI-integrated** interfaces.

This project introduces **structured configuration, observability, secure authentication, enhanced persona handling, and MCP interoperability**—transforming Whisperwynd into a resilient and extensible AI-ready platform.

## Key Features

- **Persona-Driven Storytelling** - Rich character profiles with avatars and metadata
- **FastAPI Backend** - Lightweight, modern Python web framework
- **AI Integration** - MCP server for seamless AI tool integration
- **Observability** - Built-in health checks and runtime metrics
- **Secure Authentication** - Environment-based configuration
- **Adaptive Cards** - Dynamic UI components for personas
- **Hot Reload** - Developer-friendly auto-reload during development

## Key Contributions

### Bot Configuration (`bot.xml`)

- **Metadata Added**: bot name, description, author, maintainer, version
- **Authentication Externalized**: Sensitive values (`clientId`, `clientSecret`) moved to environment variables:

```bash
export BOT_CLIENT_ID=your-client-id
export BOT_CLIENT_SECRET=your-client-secret
```

### Application Enhancements (`app.py`)

#### Imports & Dependencies
- Removed heavy external dependencies (Azure Blob, WeasyPrint, dotenv)
- Added lightweight modules (`json`, `datetime`, `functools.wraps`, `defaultdict`, `deque`)

#### Configuration Handling
- Environment-based configuration (no `.env` dependency)
- Startup validation to ensure required keys exist

#### Error Handling & Logging
- Structured logging for startup and runtime events
- Centralized error responses with clear debug output

#### New Endpoints
- `/health` → Application readiness check
- `/stats` → Runtime metrics (requests, failures, response times)

#### Developer Experience
- Auto-reload during development (Werkzeug + watchdog)
- Cleaner code separation with decorators and helpers

### Persona Retrieval (`GetPersonas-*.json`)

- Adaptive Card now includes **title, description, role, and avatar image**
- Introduced **health check scope** with user-friendly error messages
- Updated schema for **richer persona profiles**

### Whisperwynd MCP Server

Two complementary components:
- `mcp_server.py` → Stdio-based MCP server for AI tools (Claude, GPT)
- `mcp_web_server.py` → Web interface for human debugging & workflow validation

#### Functional Fixes
- Corrected escaped newline handling in JavaScript
- Fixed UUID conflicts in client communication
- Refined web server code for stability

#### MCP Advantages
- Protocol standardization (ecosystem-ready)
- Auto-discovery of tools/resources (`list_tools`, `list_resources`)
- Structured error handling & logging
- Seamless integration with AI IDEs (VS Code, Cursor) and AI agents

## Installation

```bash
# Clone repository
https://github.com/MITHRADEVIK3009/Whisperwynd-Forge.git
cd whisperwynd

# Set environment variables
export BOT_CLIENT_ID=your-client-id
export BOT_CLIENT_SECRET=your-client-secret

# Install dependencies
pip install -r requirements.txt

# Run FastAPI app
uvicorn app:app --reload
```

## Usage

### Basic Setup

1. **Start the main application:**
   ```bash
   uvicorn app:app --reload
   ```

2. **Access the application:**
   - App: `http://localhost:8000`
   

### Health Monitoring

- **Health Check:** Visit `/health` → check readiness
- **Runtime Metrics:** Visit `/stats` → view runtime metrics

### MCP Integration

1. **Launch MCP server:**
   ```bash
   python mcp_server.py
   ```

2. **Web interface for MCP debugging:**
   ```bash
   python mcp_web_server.py
   ```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint |
| `/health` | GET | Application health check |
| `/stats` | GET | Runtime statistics |
| `/personas` | GET | Retrieve persona profiles |

## Configuration

### Environment Variables

```bash
# Required
BOT_CLIENT_ID=your-client-id
BOT_CLIENT_SECRET=your-client-secret

# Optional
DEBUG=true
LOG_LEVEL=INFO
```

### Bot Configuration (`bot.xml`)

The bot configuration includes metadata and authentication settings:

```xml
<bot>
  <metadata>
    <n>Whisperwynd</n>
    <description>Interactive storytelling application</description>
    <version>1.0.0</version>
  </metadata>
  <auth>
    <clientId>${BOT_CLIENT_ID}</clientId>
    <clientSecret>${BOT_CLIENT_SECRET}</clientSecret>
  </auth>
</bot>
```

## Development

### Prerequisites

- Python 3.8+
- FastAPI
- Uvicorn
- Required dependencies (see `requirements.txt`)

### Development Mode

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run with auto-reload
uvicorn app:app --reload --debug

# Run MCP server in development
python mcp_server.py --debug
```

### Code Structure

```
Whisperwynd-Forge-main/
├── app/
│   ├── static/
│   │   └── generated_images/
│   ├── templates/
│   └── __pycache__/
├── copilit-agent/
│   ├── Assets/
│   ├── botcomponents/
│   │   └── default components/
│   ├── bots/
│   │   └── Default_whisperwyndChatbot/
│   └── Workflows/
├── Images/
├── app.py                 # Main FastAPI application
├── bot.xml               # Bot configuration
├── mcp_server.py         # MCP stdio server
├── mcp_web_server.py     # MCP web interface
├── GetPersonas-*.json    # Persona Adaptive Cards
├── requirements.txt      # Dependencies
└── README.md            # This file
```

## Future Directions

- **Expand persona metadata** with abilities and backstories
- **Add persistence layer** (Postgres or vector DB) for long-term state
- **Extend MCP tools** for richer storytelling workflows
- **Enhanced UI** with more interactive Adaptive Cards
- **Advanced search** and filtering for personas
- **Mobile-responsive** design improvements
- **Enhanced security** with OAuth2/JWT authentication

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code style
- Add tests for new features
- Update documentation for API changes
- Ensure all tests pass before submitting PR

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[Back to top](#whisperwynd)
