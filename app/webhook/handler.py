"""
FastAPI webhook handler for Lava.top payment notifications.
"""

import json
import logging
import secrets
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# Import webhook settings directly from local file
from app.webhook.settings import webhook_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="AI Girlfriend Webhook", version="1.0.0")

# Basic Auth setup
security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify Basic Auth credentials for webhook security."""
    correct_username = secrets.compare_digest(credentials.username, webhook_settings.webhook_username)
    correct_password = secrets.compare_digest(credentials.password, webhook_settings.webhook_password)
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Girlfriend Webhook Service", "status": "running"}


@app.get("/health")
async def health_check():
    """Simple health check without payment service initialization."""
    return {
        "status": "healthy",
        "service": "webhook",
        "bot_name": webhook_settings.bot_name
    }


async def process_payment_webhook_directly(webhook_data: dict) -> tuple[bool, str]:
    """Process webhook directly without payment service to avoid import issues."""
    try:
        # Extract data based on PurchaseWebhookLog schema
        event_type = webhook_data.get("eventType")
        contract_id = webhook_data.get("contractId")
        status = webhook_data.get("status")
        buyer_email = webhook_data.get("buyer", {}).get("email")
        amount = webhook_data.get("amount")
        currency = webhook_data.get("currency")
        
        if not contract_id:
            logger.error("No contractId in webhook data")
            return False, "No contractId"
        
        logger.info(f"Processing webhook: eventType={event_type}, contractId={contract_id}, status={status}")
        
        # Create database session directly
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        from sqlalchemy import select, update
        
        # Import models
        from app.database.models import Payment, PaymentTransaction, UserProfile
        
        # Create engine using webhook settings
        engine = create_async_engine(
            webhook_settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        # Create session maker
        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session_maker() as session:
            # Find payment by Lava invoice ID (contractId from webhook)
            result = await session.execute(
                select(Payment).where(Payment.lava_invoice_id == contract_id)
            )
            payment = result.scalar_one_or_none()
            
            if not payment:
                logger.error(f"Payment not found for contractId: {contract_id}")
                return False, "Payment not found"
            
            # Log webhook transaction
            transaction = PaymentTransaction.create_transaction(
                payment_id=payment.id,
                transaction_type="webhook",
                status="success",
                message=f"Webhook received: {event_type}, status: {status}",
                lava_response=json.dumps(webhook_data)
            )
            session.add(transaction)
            
            # Process payment based on event type and status
            if event_type == "payment.success" and status == "completed" and not payment.is_paid():
                # Mark payment as paid
                payment.mark_as_paid()
                
                # Add tokens directly to user balance
                stmt = (
                    update(UserProfile)
                    .where(UserProfile.chat_id == payment.chat_id)
                    .values(loan_balance=UserProfile.loan_balance + payment.tokens_to_receive)
                )
                result = await session.execute(stmt)
                
                if result.rowcount > 0:
                    logger.info(f"Added {payment.tokens_to_receive} tokens to user {payment.chat_id} via webhook")
                else:
                    logger.error(f"User not found for payment: {payment.chat_id}")
                
                await session.commit()
                
                logger.info(f"Payment completed via webhook: contractId={contract_id}, amount={amount} {currency}")
                return True, "Payment processed"
                
            elif event_type == "payment.failed" and status == "failed" and payment.is_pending():
                payment.mark_as_failed()
                await session.commit()
                
                logger.info(f"Payment failed via webhook: contractId={contract_id}, status={status}")
                return True, "Payment status updated"
            else:
                await session.commit()
                logger.info(f"Webhook processed but no action taken: eventType={event_type}, status={status}")
                return True, "Webhook received"
                
    except Exception as e:
        logger.error(f"Error processing webhook directly: {e}")
        return False, f"Error: {e}"


@app.post("/webhook/lava")
async def lava_webhook(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(verify_credentials)
):
    """Handle Lava.top payment webhook notifications."""
    try:
        # Get request body and signature
        body = await request.body()
        body_str = body.decode('utf-8')
        signature = request.headers.get('X-Signature', '')
        
        logger.info(f"Received webhook: {len(body_str)} bytes, signature: {signature[:20]}...")
        logger.info(f"Webhook body: {body_str}")
        
        # Parse webhook data
        webhook_data = json.loads(body_str)
        
        # Process webhook directly
        success, message = await process_payment_webhook_directly(webhook_data)
        
        if success:
            logger.info(f"Webhook processed successfully: {message}")
            return {"status": "success", "message": message}
        else:
            logger.error(f"Webhook processing failed: {message}")
            raise HTTPException(status_code=400, detail=message)
            
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001) 