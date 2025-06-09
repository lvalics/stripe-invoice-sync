# Stripe Invoice Sync Dashboard

A React-based dashboard for monitoring and managing Stripe invoice synchronization with Romanian invoice providers (ANAF, SmartBill).

## Features

- **Dashboard Overview**: Real-time statistics and recent activity
- **Invoice Management**: Browse, filter, and search through all processed invoices
- **Invoice Details**: View complete invoice information, processing history, and XML content
- **Retry Queue**: Manage failed invoices and retry processing
- **Provider Status**: Monitor provider connections and performance metrics

## Setup

1. Install dependencies:
```bash
cd frontend/dashboard
npm install
```

2. Configure API endpoint:
Create or modify `.env` file:
```
REACT_APP_API_URL=http://localhost:8000
```

3. Start the development server:
```bash
npm start
```

The dashboard will be available at `http://localhost:3000`

## Development

### Available Scripts

- `npm start` - Run development server
- `npm build` - Build for production
- `npm test` - Run tests

### Project Structure

```
dashboard/
├── src/
│   ├── api/           # API client and types
│   ├── components/    # Reusable components
│   ├── pages/         # Page components
│   └── App.tsx        # Main app component
├── public/
└── package.json
```

## Production Build

To create a production build:

```bash
npm run build
```

The build artifacts will be stored in the `build/` directory.

## API Integration

The dashboard communicates with the backend API running on port 8000 by default. Ensure the backend is running before starting the dashboard.

### Required Backend Endpoints

- `/api/dashboard/stats` - Dashboard statistics
- `/api/dashboard/invoices` - Invoice list and filtering
- `/api/dashboard/invoices/{id}` - Invoice details
- `/api/dashboard/invoices/{id}/history` - Processing history
- `/api/dashboard/retry-queue` - Retry queue management
- `/api/providers` - Provider list and validation