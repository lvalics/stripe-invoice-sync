"""
Dashboard API endpoints for the React frontend
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.database import get_db
from app.db.models import ProcessedInvoice as Invoice, ProcessingHistory, RetryQueue
from app.config import settings

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard statistics including totals and provider breakdowns"""
    try:
        # Total invoices and amount
        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
        total_amount = db.query(func.sum(Invoice.amount)).scalar() or 0
        
        # Provider statistics
        provider_stats = []
        providers = ["anaf", "smartbill"]  # Get from configured providers
        
        for provider in providers:
            total = db.query(func.count(Invoice.id)).filter(
                Invoice.provider == provider
            ).scalar() or 0
            
            successful = db.query(func.count(Invoice.id)).filter(
                and_(
                    Invoice.provider == provider,
                    Invoice.status.in_(["completed", "success"])
                )
            ).scalar() or 0
            
            failed = db.query(func.count(Invoice.id)).filter(
                and_(
                    Invoice.provider == provider,
                    Invoice.status.in_(["failed", "error"])
                )
            ).scalar() or 0
            
            pending = db.query(func.count(Invoice.id)).filter(
                and_(
                    Invoice.provider == provider,
                    Invoice.status.in_(["pending", "processing"])
                )
            ).scalar() or 0
            
            success_rate = (successful / total * 100) if total > 0 else 0
            
            provider_stats.append({
                "provider": provider,
                "total_invoices": total,
                "successful": successful,
                "failed": failed,
                "pending": pending,
                "success_rate": success_rate
            })
        
        # Recent activity (last 10 processing history entries)
        recent_activity = db.query(ProcessingHistory).order_by(
            ProcessingHistory.started_at.desc()
        ).limit(10).all()
        
        recent_activity_data = [
            {
                "id": activity.id,
                "invoice_id": activity.invoice_id,
                "action": activity.action,
                "status": activity.status,
                "error_message": activity.error_message,
                "created_at": activity.started_at.isoformat()
            }
            for activity in recent_activity
        ]
        
        return {
            "total_invoices": total_invoices,
            "total_amount": total_amount,
            "providers": provider_stats,
            "recent_activity": recent_activity_data
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")


@router.get("/invoices")
async def get_invoices(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get filtered list of invoices"""
    try:
        query = db.query(Invoice)
        
        if provider:
            query = query.filter(Invoice.provider == provider)
        
        if status:
            query = query.filter(Invoice.status == status)
        
        if start_date:
            start = datetime.fromisoformat(start_date)
            query = query.filter(Invoice.created_at >= start)
        
        if end_date:
            end = datetime.fromisoformat(end_date)
            query = query.filter(Invoice.created_at <= end)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                Invoice.stripe_id.like(search_pattern) |
                Invoice.customer_email.like(search_pattern)
            )
        
        invoices = query.order_by(Invoice.created_at.desc()).all()
        
        return [
            {
                "id": invoice.id,
                "stripe_invoice_id": invoice.stripe_id,
                "provider": invoice.provider,
                "status": invoice.status,
                "invoice_number": invoice.provider_invoice_id,
                "customer_name": invoice.customer_id,
                "customer_email": invoice.customer_email,
                "customer_tax_id": invoice.customer_tax_id,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "created_at": invoice.created_at.isoformat(),
                "updated_at": invoice.updated_at.isoformat(),
                "error_message": invoice.last_error,
                "pdf_url": None,
                "xml_content": None
            }
            for invoice in invoices
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get invoices: {str(e)}")


@router.get("/invoices/{invoice_id}")
async def get_invoice_by_id(invoice_id: int, db: Session = Depends(get_db)):
    """Get single invoice by ID"""
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        return {
            "id": invoice.id,
            "stripe_invoice_id": invoice.stripe_invoice_id,
            "provider": invoice.provider,
            "status": invoice.status,
            "invoice_number": invoice.invoice_number,
            "customer_name": invoice.customer_name,
            "customer_email": invoice.customer_email,
            "customer_tax_id": invoice.customer_tax_id,
            "amount": invoice.amount,
            "currency": invoice.currency,
            "created_at": invoice.created_at.isoformat(),
            "updated_at": invoice.updated_at.isoformat(),
            "error_message": invoice.error_message,
            "pdf_url": invoice.pdf_url,
            "xml_content": invoice.xml_content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get invoice: {str(e)}")


@router.get("/invoices/{invoice_id}/history")
async def get_invoice_history(invoice_id: int, db: Session = Depends(get_db)):
    """Get processing history for an invoice"""
    try:
        history = db.query(ProcessingHistory).filter(
            ProcessingHistory.invoice_id == invoice_id
        ).order_by(ProcessingHistory.started_at.desc()).all()
        
        return [
            {
                "id": h.id,
                "invoice_id": h.invoice_id,
                "action": h.action,
                "status": h.status,
                "error_message": h.error_message,
                "created_at": h.started_at.isoformat()
            }
            for h in history
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get invoice history: {str(e)}")


@router.post("/invoices/{invoice_id}/retry")
async def retry_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Retry processing for a failed invoice"""
    try:
        invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        if invoice.status not in ["failed", "error"]:
            raise HTTPException(
                status_code=400, 
                detail="Can only retry failed invoices"
            )
        
        # Add to retry queue
        retry_item = RetryQueue(
            invoice_id=invoice_id,
            stripe_id=invoice.stripe_id,
            provider=invoice.provider,
            retry_count=0,
            retry_after=datetime.utcnow(),
            max_retries=3
        )
        db.add(retry_item)
        db.commit()
        
        return {"message": "Invoice added to retry queue"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to retry invoice: {str(e)}")


@router.get("/retry-queue")
async def get_retry_queue(db: Session = Depends(get_db)):
    """Get all items in the retry queue"""
    try:
        queue_items = db.query(RetryQueue).order_by(
            RetryQueue.retry_after
        ).all()
        
        return [
            {
                "id": item.id,
                "invoice_id": item.invoice_id,
                "retry_count": item.retry_count,
                "next_retry_at": item.retry_after.isoformat(),
                "max_retries": item.max_retries,
                "error_message": item.last_error,
                "created_at": item.created_at.isoformat()
            }
            for item in queue_items
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get retry queue: {str(e)}")


@router.delete("/retry-queue/{item_id}")
async def remove_from_retry_queue(item_id: int, db: Session = Depends(get_db)):
    """Remove an item from the retry queue"""
    try:
        item = db.query(RetryQueue).filter(RetryQueue.id == item_id).first()
        
        if not item:
            raise HTTPException(status_code=404, detail="Retry queue item not found")
        
        db.delete(item)
        db.commit()
        
        return {"message": "Item removed from retry queue"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove from retry queue: {str(e)}")