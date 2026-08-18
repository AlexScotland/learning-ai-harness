# 🤖 AI Assistant Chat

A minimal, fast chat interface for the learning-ai-harness AI assistant. Built with **Next.js 14** (App Router), **React 18**, **TypeScript**, and **CSS Modules** with a **dark theme** design system.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| UI | React 18 + CSS Modules |
| Theme | Dark theme (design tokens in `globals.css`) |
| Language | TypeScript 5 (strict) |
| Build output | `standalone` (self-contained `server.js`) |
| Container | Docker (multi-stage, `node:20-alpine`) |

## Getting Started

### Prerequisites

- Node.js 20+
- npm 10+

### Install & Run (development)

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Production Build

```bash
npm run build
npm start
```

### Docker

```bash
# Build
docker build -t chat-ui .

# Run
docker run -p 3000:3000 chat-ui
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the backend API. Inlined into the client bundle at build time. |

Copy `.env.example` to `.env.local` and adjust as needed:

```bash
cp .env.example .env.local
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the development server with hot reload |
| `npm run build` | Create a production build (standalone output) |
| `npm start` | Start the production server |
| `npm run lint` | Run ESLint |

## Project Structure

```
├── app/                  # Next.js App Router
│   ├── layout.tsx        # Root layout (metadata, global CSS)
│   ├── page.tsx          # Chat page
│   ├── not-found.tsx     # 404 page
│   ├── error.tsx         # Error boundary
│   ├── global-error.tsx  # Root error boundary
│   ├── loading.tsx       # Loading state
│   ├── icon.svg          # Favicon
│   ├── globals.css       # Design tokens + global styles
│   └── *.module.css      # Component-scoped styles
├── components/           # Reusable UI components
│   ├── ChatInput.tsx     # Message input + send button
│   └── MessageList.tsx   # Scrollable message list
├── hooks/
│   └── useChat.ts        # Chat state + API communication
├── public/               # Static assets
├── next.config.js        # Next.js config (standalone output)
├── tsconfig.json         # TypeScript config
├── package.json          # Dependencies + scripts
├── Dockerfile            # Multi-stage Docker build
└── .dockerignore         # Docker build context exclusions
```

## API

The chat UI sends messages to:

```
POST {NEXT_PUBLIC_API_URL}/api/chat
Content-Type: application/json

{ "message": "Hello!" }
```

Expected response:

```json
{ "answer": "Hi there! How can I help?" }
```

The client also accepts `response` or `message` as alternative field names.
