import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Process from './pages/Process';
import Invoices from './pages/Invoices';
import InvoiceDetail from './pages/InvoiceDetail';
import RetryQueue from './pages/RetryQueue';
import Providers from './pages/Providers';

const theme = createTheme({
  palette: {
    primary: {
      main: '#635BFF',
    },
    secondary: {
      main: '#0A2540',
    },
    background: {
      default: '#F6F9FC',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/process" element={<Process />} />
            <Route path="/invoices" element={<Invoices />} />
            <Route path="/invoices/:id" element={<InvoiceDetail />} />
            <Route path="/retry-queue" element={<RetryQueue />} />
            <Route path="/providers" element={<Providers />} />
          </Routes>
        </Layout>
      </Router>
    </ThemeProvider>
  );
}

export default App;
