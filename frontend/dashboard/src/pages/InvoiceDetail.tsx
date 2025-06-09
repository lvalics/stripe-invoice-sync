import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tabs,
  Tab,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { api, Invoice, ProcessingHistory } from '../api/client';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div hidden={value !== index} {...other}>
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

export default function InvoiceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [history, setHistory] = useState<ProcessingHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabValue, setTabValue] = useState(0);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (id) {
      loadInvoiceData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadInvoiceData = async () => {
    try {
      setLoading(true);
      const [invoiceData, historyData] = await Promise.all([
        api.invoices.getById(parseInt(id!)),
        api.invoices.getHistory(parseInt(id!)),
      ]);
      setInvoice(invoiceData);
      setHistory(historyData);
      setError(null);
    } catch (err) {
      setError('Failed to load invoice details');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!invoice) return;
    
    try {
      setRetrying(true);
      await api.invoices.retry(invoice.id);
      await loadInvoiceData();
    } catch (err) {
      console.error('Failed to retry invoice:', err);
    } finally {
      setRetrying(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success':
        return 'success';
      case 'failed':
      case 'error':
        return 'error';
      case 'pending':
      case 'processing':
        return 'warning';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error || !invoice) {
    return (
      <Box>
        <Button
          startIcon={<ArrowBackIcon />}
          onClick={() => navigate('/invoices')}
          sx={{ mb: 2 }}
        >
          Back to Invoices
        </Button>
        <Alert severity="error">{error || 'Invoice not found'}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box display="flex" alignItems="center" gap={2}>
          <IconButton onClick={() => navigate('/invoices')}>
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h4">Invoice Details</Typography>
        </Box>
        <Box display="flex" gap={1}>
          {invoice.pdf_url && (
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              href={invoice.pdf_url}
              target="_blank"
            >
              Download PDF
            </Button>
          )}
          {invoice.status === 'failed' && (
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
              disabled={retrying}
            >
              Retry
            </Button>
          )}
        </Box>
      </Box>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 8 }}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">Invoice Information</Typography>
                <Chip
                  label={invoice.status}
                  color={getStatusColor(invoice.status)}
                />
              </Box>
              <Grid container spacing={2}>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Stripe Invoice ID
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {invoice.stripe_invoice_id}
                  </Typography>
                </Grid>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Invoice Number
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {invoice.invoice_number || 'N/A'}
                  </Typography>
                </Grid>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Provider
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {invoice.provider.toUpperCase()}
                  </Typography>
                </Grid>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Amount
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {invoice.currency.toUpperCase()} {(invoice.amount / 100).toFixed(2)}
                  </Typography>
                </Grid>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Created
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {format(new Date(invoice.created_at), 'MMM dd, yyyy HH:mm:ss')}
                  </Typography>
                </Grid>
                <Grid size={6}>
                  <Typography variant="body2" color="textSecondary">
                    Updated
                  </Typography>
                  <Typography variant="body1" gutterBottom>
                    {format(new Date(invoice.updated_at), 'MMM dd, yyyy HH:mm:ss')}
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Customer Information
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Name
              </Typography>
              <Typography variant="body1" gutterBottom>
                {invoice.customer_name || 'N/A'}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Email
              </Typography>
              <Typography variant="body1" gutterBottom>
                {invoice.customer_email || 'N/A'}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Tax ID
              </Typography>
              <Typography variant="body1">
                {invoice.customer_tax_id || 'N/A'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {invoice.error_message && (
          <Grid size={12}>
            <Alert severity="error">
              <Typography variant="subtitle2">Error Message</Typography>
              <Typography variant="body2">{invoice.error_message}</Typography>
            </Alert>
          </Grid>
        )}

        <Grid size={12}>
          <Paper>
            <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
              <Tab label="Processing History" />
              {invoice.xml_content && <Tab label="XML Content" />}
            </Tabs>
            
            <TabPanel value={tabValue} index={0}>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Action</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Message</TableCell>
                      <TableCell>Date</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell>{item.action}</TableCell>
                        <TableCell>
                          <Chip
                            label={item.status}
                            color={getStatusColor(item.status)}
                            size="small"
                          />
                        </TableCell>
                        <TableCell>{item.error_message || '-'}</TableCell>
                        <TableCell>
                          {format(new Date(item.created_at), 'MMM dd, yyyy HH:mm:ss')}
                        </TableCell>
                      </TableRow>
                    ))}
                    {history.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={4} align="center">
                          No processing history available
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </TabPanel>
            
            {invoice.xml_content && (
              <TabPanel value={tabValue} index={1}>
                <Box
                  component="pre"
                  sx={{
                    backgroundColor: '#f5f5f5',
                    p: 2,
                    borderRadius: 1,
                    overflow: 'auto',
                    maxHeight: '600px',
                    fontSize: '0.875rem',
                  }}
                >
                  <code>{invoice.xml_content}</code>
                </Box>
              </TabPanel>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}