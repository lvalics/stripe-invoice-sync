import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  DialogContentText,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Visibility as VisibilityIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { api, RetryQueueItem, Invoice } from '../api/client';

export default function RetryQueue() {
  const navigate = useNavigate();
  const [queueItems, setQueueItems] = useState<RetryQueueItem[]>([]);
  const [invoices, setInvoices] = useState<Map<number, Invoice>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [itemToDelete, setItemToDelete] = useState<RetryQueueItem | null>(null);

  useEffect(() => {
    loadRetryQueue();
  }, []);

  const loadRetryQueue = async () => {
    try {
      setLoading(true);
      const data = await api.retryQueue.getAll();
      setQueueItems(data);
      
      // Load invoice details for each queue item
      const invoiceMap = new Map<number, Invoice>();
      await Promise.all(
        data.map(async (item) => {
          try {
            const invoice = await api.invoices.getById(item.invoice_id);
            invoiceMap.set(item.invoice_id, invoice);
          } catch (err) {
            console.error(`Failed to load invoice ${item.invoice_id}:`, err);
          }
        })
      );
      setInvoices(invoiceMap);
      
      setError(null);
    } catch (err) {
      setError('Failed to load retry queue');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!itemToDelete) return;
    
    try {
      await api.retryQueue.remove(itemToDelete.id);
      setDeleteDialogOpen(false);
      setItemToDelete(null);
      loadRetryQueue();
    } catch (err) {
      console.error('Failed to remove item from retry queue:', err);
    }
  };

  const openDeleteDialog = (item: RetryQueueItem) => {
    setItemToDelete(item);
    setDeleteDialogOpen(true);
  };

  const getRetryTimeRemaining = (nextRetryAt: string) => {
    const now = new Date();
    const retryTime = new Date(nextRetryAt);
    const diff = retryTime.getTime() - now.getTime();
    
    if (diff <= 0) return 'Ready';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Retry Queue</Typography>
        <Box>
          <Typography variant="body2" color="textSecondary">
            {queueItems.length} items in queue
          </Typography>
          <IconButton onClick={loadRetryQueue} color="primary">
            <RefreshIcon />
          </IconButton>
        </Box>
      </Box>

      {queueItems.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="textSecondary">
            No items in the retry queue
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Invoice</TableCell>
                <TableCell>Customer</TableCell>
                <TableCell>Provider</TableCell>
                <TableCell>Retry Count</TableCell>
                <TableCell>Next Retry</TableCell>
                <TableCell>Error</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {queueItems.map((item) => {
                const invoice = invoices.get(item.invoice_id);
                return (
                  <TableRow key={item.id}>
                    <TableCell>
                      {invoice?.stripe_invoice_id || `#${item.invoice_id}`}
                    </TableCell>
                    <TableCell>
                      {invoice ? (
                        <Box>
                          <Typography variant="body2">{invoice.customer_name}</Typography>
                          <Typography variant="caption" color="textSecondary">
                            {invoice.customer_email}
                          </Typography>
                        </Box>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      {invoice?.provider.toUpperCase() || '-'}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={`${item.retry_count} / ${item.max_retries}`}
                        color={item.retry_count >= item.max_retries - 1 ? 'error' : 'default'}
                        size="small"
                      />
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">
                          {format(new Date(item.next_retry_at), 'MMM dd, yyyy HH:mm')}
                        </Typography>
                        <Typography variant="caption" color="textSecondary">
                          {getRetryTimeRemaining(item.next_retry_at)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography
                        variant="body2"
                        sx={{
                          maxWidth: 200,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={item.error_message}
                      >
                        {item.error_message || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/invoices/${item.invoice_id}`)}
                      >
                        <VisibilityIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => openDeleteDialog(item)}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Remove from Retry Queue</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to remove this invoice from the retry queue? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDelete} color="error">
            Remove
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}