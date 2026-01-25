# Rookie Demo Frontend

Production-quality React SPA for demonstrating the Personal Tax Agent to CPAs.

## Quick Start

### Prerequisites

1. **Backend**: Start the FastAPI server (from project root):
   ```bash
   uv run uvicorn src.main:app --reload --port 8001
   ```

2. **Frontend**: Start the Vite dev server:
   ```bash
   cd frontend
   npm install  # first time only
   npm run dev
   ```

3. Open http://localhost:5173 in your browser

### Demo Flow

1. **Upload Documents**: Drag W-2s and 1099 PDFs/images onto the upload zone
2. **Enter Client Info**: Client name, tax year, filing status
3. **Process**: Click "Process Documents" to start
4. **Watch Progress**: Real-time SSE updates show each processing stage
5. **View Results**: 
   - Income breakdown and tax calculation
   - Prior year variance alerts
   - Confidence indicators
6. **Download Outputs**: Drake worksheet (Excel) and preparer notes (Markdown)

## Tech Stack

- React 18 + TypeScript
- Vite
- Tailwind CSS
- TanStack Query (React Query)
- Radix UI primitives
- motion/react (animations)
- Lucide icons

## Design

Following the Rookie Website Design Brief:
- Warm amber/gold accent (#d97706) - NOT blue
- Lexend headlines, IBM Plex Sans body, JetBrains Mono for numbers
- Professional but approachable aesthetic
- Shows actual work output, not AI hype

## Project Structure

```
frontend/
├── src/
│   ├── api/demo.ts          # API client with SSE support
│   ├── components/
│   │   ├── UploadZone.tsx   # Drag-drop upload
│   │   ├── ProcessingProgress.tsx  # Real-time progress
│   │   └── ResultsPanel.tsx # Results display
│   ├── lib/utils.ts         # Utilities (cn, formatCurrency)
│   ├── types/api.ts         # TypeScript interfaces
│   └── App.tsx              # Main app flow
└── public/
    └── rookie-icon.svg      # Favicon
```

## Build for Production

```bash
npm run build
```

Output goes to `dist/`. Can be served by FastAPI in production.

## Development

```bash
npm run dev     # Start dev server with HMR
npm run build   # Production build
npm run preview # Preview production build
npm run lint    # Run ESLint
```
