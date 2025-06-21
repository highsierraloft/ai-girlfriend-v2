"""
Payment service for handling Lava.top API integration.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from urllib.parse import urljoin

import aiohttp
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_database
from app.database.models import Payment, PaymentTransaction, UserProfile

logger = logging.getLogger(__name__)


class LavaPaymentService:
    """Service for handling Lava.top payments."""
    
    def __init__(self, settings=None):
        """Initialize the Lava.top payment service."""
        if settings:
            self.settings = settings
            logger.info("Using provided settings for payment service")
        else:
            # Check if we're in webhook mode
            import os
            if os.getenv('WEBHOOK_MODE') == 'true':
                # We're in webhook context - use webhook settings directly
                from app.webhook.settings import get_webhook_settings
                self.settings = get_webhook_settings()
                logger.info("Using webhook settings for payment service (webhook mode)")
            else:
                # We're in main bot context - try to load main settings
                try:
                    from app.config.settings import get_settings
                    self.settings = get_settings()
                    logger.info("Using main settings for payment service")
                except Exception as e:
                    logger.debug(f"Could not load main settings: {e}")
                    from app.webhook.settings import get_webhook_settings
                    self.settings = get_webhook_settings()
                    logger.info("Using webhook settings for payment service (fallback)")
        
        self.api_key = self.settings.lava_api_key
        self.shop_id = self.settings.lava_shop_id
        self.api_url = self.settings.lava_api_url.rstrip('/')
        self.bot_name = getattr(self.settings, 'bot_name', 'ai-girlfriend')
        
        # Check if we're in test mode
        self.test_mode = getattr(self.settings, 'debug', False)
        
        logger.info(f"LavaPaymentService initialized for shop: {self.shop_id[:12]}...")
        
        # Initialize offer mapping - will be populated from API
        self.offer_mapping = {}
        self._offers_loaded = False
        
        # Note: Offers will be loaded on first use via ensure_offers_loaded()
        
        # Get payment packages - check if available in settings
        if hasattr(settings, 'payment_packages'):
            self.packages = settings.payment_packages
        else:
            # Default packages for webhook service
            self.packages = {
                "100": {"tokens": 100, "eur": 5, "usd": 6, "rub": 500},
                "200": {"tokens": 200, "eur": 8, "usd": 9, "rub": 800},
                "300": {"tokens": 300, "eur": 12, "usd": 13, "rub": 1000}
            }
    
    async def ensure_offers_loaded(self) -> bool:
        """
        Ensure offers are loaded from API. Call this before using get_offer_id().
        
        Returns:
            bool: True if offers are available, False otherwise
        """
        if self._offers_loaded:
            return True
            
        if self.test_mode:
            logger.info("Test mode enabled - skipping offer loading from API")
            return True
            
        success = await self._load_offers_from_api()
        if success:
            self._offers_loaded = True
        return success
    
    async def _load_offers_from_api(self) -> bool:
        """
        Load offers from Lava.top API.
        
        Returns:
            bool: True if offers loaded successfully, False otherwise
        """
        try:
            headers = {
                "X-Api-Key": self.api_key,
                "Content-Type": "application/json"
            }
            
            # Get products from Lava.top API
            url = f"{self.api_url}/api/v2/products"
            logger.info(f"Fetching offers from Lava.top API: {url}")
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Lava.top API Response 200: {json.dumps(data, ensure_ascii=False)[:500]}...")
                        
                        # Parse products and build offer mapping
                        self._parse_offers_from_response(data)
                        logger.info(f"Loaded {len(self.offer_mapping)} offer mappings from API")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Lava.top API error {response.status}: {error_text[:500]}...")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to load offers from API: {str(e)}")
            return False
    
    def _parse_offers_from_response(self, data: dict) -> None:
        """
        Parse offers from Lava.top API response and build mapping.
        
        Args:
            data: API response data
        """
        try:
            items = data.get('items', [])
            logger.info(f"Processing {len(items)} items from API response")
            
            for i, item in enumerate(items):
                logger.debug(f"Item {i}: {json.dumps(item, indent=2)}")
                
                # Check if it's a product item (not a post)
                item_type = item.get('type')
                logger.debug(f"Item {i} type: {item_type}")
                
                if item_type not in ['PRODUCT', 'DIGITAL_PRODUCT']:
                    logger.debug(f"Skipping item {i} - not a product (type: {item_type})")
                    continue
                
                # Product data is directly in the item, not in a 'data' field
                product_title = item.get('title', '').lower()
                offers = item.get('offers', [])
                
                logger.info(f"Processing product: '{product_title}' with {len(offers)} offers")
                
                if not offers:
                    logger.warning(f"No offers in product: {product_title}")
                    continue
                
                # Try to identify token packages by title and offer names
                for j, offer in enumerate(offers):
                    offer_name = offer.get('name', '').lower()
                    offer_id = offer.get('id')
                    prices = offer.get('prices', [])
                    
                    logger.debug(f"  Offer {j}: name='{offer_name}', id={offer_id}, prices={len(prices)}")
                    
                    # Identify token amount from offer name
                    tokens = None
                    if '100' in offer_name and 'токен' in offer_name:
                        tokens = '100'
                    elif '200' in offer_name and 'токен' in offer_name:
                        tokens = '200'
                    elif '300' in offer_name and 'токен' in offer_name:
                        tokens = '300'
                    
                    if not tokens:
                        logger.warning(f"Could not identify token amount from offer name: '{offer_name}'")
                        continue
                    
                    logger.info(f"Identified {tokens} tokens from offer: '{offer_name}'")
                    
                    # Process prices for this offer
                    if tokens not in self.offer_mapping:
                        self.offer_mapping[tokens] = {}
                    
                    for price in prices:
                        currency = price.get('currency')
                        if currency and offer_id:
                            self.offer_mapping[tokens][currency] = offer_id
                            logger.info(f"✅ Mapped {tokens} tokens {currency} -> {offer_id}")
                        else:
                            logger.warning(f"Missing currency or offer_id: currency={currency}, offer_id={offer_id}")
            
            logger.info(f"Final offer mapping: {self.offer_mapping}")
                            
        except Exception as e:
            logger.error(f"Error parsing offers from API response: {str(e)}")
            logger.debug(f"Response data: {json.dumps(data, indent=2)}")
    
    def generate_order_id(self) -> str:
        """Generate unique order ID."""
        timestamp = int(datetime.now().timestamp())
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.bot_name}_{timestamp}_{unique_id}"
    
    def create_signature(self, data: Dict[str, Any]) -> str:
        """Create HMAC signature for Lava.top API request."""
        # According to Lava.top docs, signature is created from sorted parameters
        sorted_params = sorted(data.items())
        
        # Create query string without signature
        query_string = "&".join([f"{key}={value}" for key, value in sorted_params if key != "signature"])
        
        # Create HMAC signature using API key as secret
        signature = hmac.new(
            self.api_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """Verify webhook signature from Lava.top."""
        expected_signature = hmac.new(
            self.settings.lava_webhook_secret.encode('utf-8'),
            body.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    async def create_invoice(
        self,
        chat_id: int,
        package_id: str,
        user_ip: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Payment]]:
        """
        Create payment invoice via Lava.top API.
        
        Args:
            chat_id: User's chat ID
            package_id: Package ID (100, 200, 300)
            user_ip: User's IP address for fraud detection
            
        Returns:
            Tuple of (success, message, payment_object)
        """
        if package_id not in self.packages:
            return False, f"Неизвестный пакет: {package_id}", None
        
        package = self.packages[package_id]
        order_id = self.generate_order_id()
        
        async for session in get_database():
            try:
                # Create payment record
                payment = Payment(
                    chat_id=chat_id,
                    amount_eur=package["eur"],
                    amount_usd=package["usd"],
                    amount_rub=package["rub"],
                    tokens_to_receive=package["tokens"],
                    lava_order_id=order_id,
                    bot_name=self.bot_name,
                    user_ip=user_ip,
                    status="pending"
                )
                
                session.add(payment)
                await session.flush()  # Get payment ID
                
                # Ensure offers are loaded from API
                await self.ensure_offers_loaded()
                
                # Check if we should use test mode (default to RUB for old method)
                use_test_mode = self.should_use_test_mode(package_id, "RUB")
                
                if use_test_mode:
                    # TEST MODE: Create mock payment
                    mock_payment_url = f"https://lava.top/pay/test_{order_id}"
                    payment.lava_invoice_id = f"test_invoice_{payment.id}"
                    payment.lava_payment_url = mock_payment_url
                    
                    # Log test transaction
                    transaction = PaymentTransaction.create_transaction(
                        payment_id=payment.id,
                        transaction_type="create_invoice",
                        status="success",
                        message="TEST MODE - Mock payment created (RUB)",
                        lava_response=f'{{"status": "success", "test_mode": true, "url": "{mock_payment_url}", "currency": "RUB", "amount": {package["rub"]}}}',
                        http_status=200
                    )
                    session.add(transaction)
                    await session.commit()
                    
                    logger.info(f"TEST MODE: Created mock invoice for chat_id={chat_id}, order_id={order_id}")
                    return True, "Тестовый счёт создан успешно", payment
                
                # PRODUCTION MODE: Get real offer ID for RUB
                offer_id = self.get_offer_id(package_id, "RUB")
                if not offer_id:
                    logger.error(f"No offer ID available for {package_id} tokens in RUB")
                    payment.mark_as_failed()
                    await session.commit()
                    return False, "Конфигурация временно недоступна", None
                
                # PRODUCTION MODE: Real API call using correct Lava.top v2 endpoints
                webhook_url = getattr(self.settings, 'lava_webhook_url', None)
                
                # Prepare invoice data according to Lava.top v2 API Swagger documentation
                invoice_data = {
                    "email": f"user_{chat_id}@{self.bot_name}.com",  # Generate email for user
                    "offerId": offer_id,  # Real offer ID from Lava.top dashboard
                    "currency": "RUB",  # Default to RUB for old method
                    "periodicity": "ONE_TIME"  # For one-time purchases
                }
                
                # Add webhook URL if available (this is not in the schema but might be accepted)
                if webhook_url:
                    invoice_data["hookUrl"] = webhook_url
                
                # Use correct Lava.top v2 API endpoint from Swagger documentation
                url = f"{self.api_url}/api/v2/invoice"
                
                logger.info(f"Creating invoice via Lava.top API: {url}")
                logger.debug(f"Invoice data: {json.dumps(invoice_data)}")
                
                # Make API request with proper authentication
                headers = {
                    "Content-Type": "application/json",
                    "X-Api-Key": self.api_key  # Required authentication header
                }
                
                async with aiohttp.ClientSession() as client_session:
                    try:
                        async with client_session.post(
                            url,
                            json=invoice_data,
                            timeout=aiohttp.ClientTimeout(total=30),
                            headers=headers
                        ) as response:
                            response_text = await response.text()
                            
                            logger.info(f"Lava.top API Response {response.status}: {response_text[:500]}...")
                            
                            # Log transaction
                            transaction = PaymentTransaction.create_transaction(
                                payment_id=payment.id,
                                transaction_type="create_invoice",
                                status="success" if response.status == 201 else "error",  # API returns 201 on success
                                message=f"HTTP {response.status}",
                                lava_response=response_text,
                                http_status=response.status
                            )
                            session.add(transaction)
                            
                            if response.status == 201:  # Swagger shows 201 for successful creation
                                try:
                                    response_data = await response.json()
                                    
                                    # Extract payment data based on InvoicePaymentParamsResponse schema
                                    payment.lava_invoice_id = response_data.get("id")
                                    payment.lava_payment_url = response_data.get("paymentUrl")
                                    
                                    # Store the order ID for tracking (our internal ID)
                                    payment.lava_order_id = order_id
                                    
                                    await session.commit()
                                    
                                    logger.info(f"Successfully created invoice for chat_id={chat_id}, order_id={order_id}")
                                    return True, "Счёт создан успешно", payment
                                        
                                except Exception as json_error:
                                    logger.error(f"JSON parse error: {json_error}")
                                    payment.mark_as_failed()
                                    await session.commit()
                                    return False, "Ошибка обработки ответа от платёжной системы", None
                            else:
                                # Handle error response
                                try:
                                    error_data = await response.json()
                                    error_msg = error_data.get("error", f"HTTP {response.status}")
                                except:
                                    error_msg = f"HTTP {response.status}: {response_text}"
                                
                                logger.error(f"Lava.top API error: {error_msg}")
                                payment.mark_as_failed()
                                await session.commit()
                                return False, f"Ошибка создания платежа: {error_msg}", None
                                    
                    except Exception as request_error:
                        logger.error(f"Request error: {request_error}")
                        payment.mark_as_failed()
                        await session.commit()
                        return False, f"Ошибка подключения к платёжной системе: {str(request_error)}", None
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating invoice: {e}")
                return False, "Внутренняя ошибка сервера", None
            break  # Exit the async for loop
    
    async def check_payment_status(self, order_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Check payment status via Lava.top API.
        
        Args:
            order_id: Our order ID
            
        Returns:
            Tuple of (success, message, payment_data)
        """
        async for session in get_database():
            try:
                # Get payment from database
                result = await session.execute(
                    select(Payment).where(Payment.lava_order_id == order_id)
                )
                payment = result.scalar_one_or_none()
                
                if not payment:
                    return False, "Платёж не найден", None
                
                if not payment.lava_invoice_id:
                    return False, "ID инвойса не найден", None
                
                # Use correct Lava.top API endpoint for getting invoice by ID from Swagger documentation
                url = f"{self.api_url}/api/v1/invoices/{payment.lava_invoice_id}"
                
                # Make API request with proper authentication
                headers = {
                    "X-Api-Key": self.api_key  # Required authentication header
                }
                
                # Make API request
                async with aiohttp.ClientSession() as client_session:
                    async with client_session.get(
                        url,
                        timeout=aiohttp.ClientTimeout(total=30),
                        headers=headers
                    ) as response:
                        response_text = await response.text()
                        
                        # Log transaction
                        transaction = PaymentTransaction.create_transaction(
                            payment_id=payment.id,
                            transaction_type="status_check",
                            status="success" if response.status == 200 else "error",
                            message=f"HTTP {response.status}",
                            lava_response=response_text,
                            http_status=response.status
                        )
                        session.add(transaction)
                        
                        if response.status == 200:
                            response_data = await response.json()
                            
                            # Extract data based on InvoiceResponseV2 schema
                            payment_status = response_data.get("status")  # InvoiceStatus enum
                            contract_status = response_data.get("receipt", {}).get("status")  # ContractStatusDto enum
                            
                            # Update payment status if needed
                            if payment_status == "COMPLETED" and not payment.is_paid():
                                await self._process_successful_payment(session, payment)
                            elif payment_status in ["FAILED"] and payment.is_pending():
                                payment.mark_as_failed()
                            
                            await session.commit()
                            return True, f"Статус: {payment_status}", response_data
                        else:
                            # Handle error response
                            try:
                                error_data = await response.json()
                                error_msg = error_data.get("error", f"HTTP {response.status}")
                            except:
                                error_msg = f"HTTP {response.status}: {response_text}"
                            
                            await session.commit()
                            return False, f"Ошибка проверки статуса: {error_msg}", None
                            
            except Exception as e:
                await session.rollback()
                logger.error(f"Error checking payment status: {e}")
                return False, "Внутренняя ошибка сервера", None
            break
    
    async def _get_webhook_database_session(self):
        """Get database session for webhook processing."""
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
        
        # Create engine using webhook settings
        engine = create_async_engine(
            self.settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        # Create session maker
        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        return async_session_maker()
    
    async def process_webhook(self, body: str, signature: str) -> Tuple[bool, str]:
        """
        Process webhook from Lava.top.
        
        Args:
            body: Webhook body
            signature: Webhook signature
            
        Returns:
            Tuple of (success, message)
        """
        # Verify signature if webhook secret is configured
        if self.settings.lava_webhook_secret and not self.verify_webhook_signature(body, signature):
            logger.warning("Invalid webhook signature")
            return False, "Invalid signature"
        
        try:
            webhook_data = json.loads(body)
            
            # Extract data based on PurchaseWebhookLog schema
            event_type = webhook_data.get("eventType")  # WebhookEventType enum
            contract_id = webhook_data.get("contractId")  # UUID of the contract
            status = webhook_data.get("status")  # ContractStatusDto enum
            buyer_email = webhook_data.get("buyer", {}).get("email")
            amount = webhook_data.get("amount")
            currency = webhook_data.get("currency")
            
            if not contract_id:
                logger.error("No contractId in webhook data")
                return False, "No contractId"
            
            logger.info(f"Processing webhook: eventType={event_type}, contractId={contract_id}, status={status}")
            
            # Use webhook-specific database session
            session = await self._get_webhook_database_session()
            try:
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
                    lava_response=body
                )
                session.add(transaction)
                
                # Process payment based on event type and status
                if event_type == "payment.success" and status == "completed" and not payment.is_paid():
                    await self._process_successful_payment(session, payment)
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
                    
            finally:
                await session.close()
                    
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return False, f"Error: {e}"
    
    async def _process_successful_payment(self, session: AsyncSession, payment: Payment) -> None:
        """Process successful payment - add tokens to user balance."""
        # Mark payment as paid
        payment.mark_as_paid()
        
        # Add tokens directly to user balance without UserService
        try:
            from sqlalchemy import update
            from app.database.models import UserProfile
            
            # Update user balance directly
            stmt = (
                update(UserProfile)
                .where(UserProfile.chat_id == payment.chat_id)
                .values(loan_balance=UserProfile.loan_balance + payment.tokens_to_receive)
            )
            result = await session.execute(stmt)
            
            if result.rowcount > 0:
                logger.info(
                    f"Added {payment.tokens_to_receive} tokens to user {payment.chat_id} via webhook"
                )
            else:
                logger.error(f"User not found for payment: {payment.chat_id}")
        except Exception as e:
            logger.error(f"Error adding tokens to user {payment.chat_id}: {e}")
    
    async def get_payment_by_order_id(self, order_id: str) -> Optional[Payment]:
        """Get payment by order ID."""
        async for session in get_database():
            result = await session.execute(
                select(Payment).where(Payment.lava_order_id == order_id)
            )
            return result.scalar_one_or_none()
    
    async def get_user_payments(self, chat_id: int, limit: int = 10) -> list[Payment]:
        """Get user's payment history."""
        async for session in get_database():
            result = await session.execute(
                select(Payment)
                .where(Payment.chat_id == chat_id)
                .order_by(Payment.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    
    async def create_invoice_with_currency(
        self,
        chat_id: int,
        package_id: str,
        currency: str,
        user_ip: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Payment]]:
        """
        Create payment invoice via Lava.top API with currency selection.
        
        Args:
            chat_id: User's chat ID
            package_id: Package ID (100, 200, 300)
            currency: Currency code (RUB, EUR, USD)
            user_ip: User's IP address for fraud detection
            
        Returns:
            Tuple of (success, message, payment_object)
        """
        if package_id not in self.packages:
            return False, f"Неизвестный пакет: {package_id}", None
        
        if currency.upper() not in ["RUB", "EUR", "USD"]:
            return False, f"Неподдерживаемая валюта: {currency}", None
        
        package = self.packages[package_id]
        currency_key = currency.lower()
        amount = package[currency_key]
        order_id = self.generate_order_id()
        
        async for session in get_database():
            try:
                # Create payment record
                payment = Payment(
                    chat_id=chat_id,
                    amount_eur=package["eur"],
                    amount_usd=package["usd"],
                    amount_rub=package["rub"],
                    tokens_to_receive=package["tokens"],
                    lava_order_id=order_id,
                    bot_name=self.bot_name,
                    user_ip=user_ip,
                    status="pending"
                )
                
                session.add(payment)
                await session.flush()  # Get payment ID
                
                # Ensure offers are loaded from API
                await self.ensure_offers_loaded()
                
                # Check if we should use test mode
                use_test_mode = self.should_use_test_mode(package_id, currency)
                
                if use_test_mode:
                    # TEST MODE: Create mock payment
                    mock_payment_url = f"https://lava.top/pay/test_{order_id}"
                    payment.lava_invoice_id = f"test_invoice_{payment.id}"
                    payment.lava_payment_url = mock_payment_url
                    
                    # Log test transaction
                    transaction = PaymentTransaction.create_transaction(
                        payment_id=payment.id,
                        transaction_type="create_invoice",
                        status="success",
                        message=f"TEST MODE - Mock payment created ({currency.upper()}: {amount})",
                        lava_response=f'{{"status": "success", "test_mode": true, "url": "{mock_payment_url}", "currency": "{currency.upper()}", "amount": {amount}}}',
                        http_status=200
                    )
                    session.add(transaction)
                    await session.commit()
                    
                    logger.info(f"TEST MODE: Created mock invoice for chat_id={chat_id}, order_id={order_id}, currency={currency.upper()}, amount={amount}")
                    return True, f"Тестовый счёт создан успешно ({currency.upper()}: {amount})", payment
                
                # PRODUCTION MODE: Get real offer ID
                offer_id = self.get_offer_id(package_id, currency)
                if not offer_id:
                    # This shouldn't happen due to should_use_test_mode check, but just in case
                    logger.error(f"No offer ID available for {package_id} tokens in {currency}")
                    payment.mark_as_failed()
                    await session.commit()
                    return False, f"Конфигурация для {currency} временно недоступна", None
                
                # PRODUCTION MODE: Real API call using correct Lava.top v2 endpoints
                webhook_url = getattr(self.settings, 'lava_webhook_url', None)
                
                # Prepare invoice data according to Lava.top v2 API Swagger documentation
                invoice_data = {
                    "email": f"user_{chat_id}@{self.bot_name}.com",  # Generate email for user
                    "offerId": offer_id,  # Real offer ID from Lava.top dashboard
                    "currency": currency.upper(),
                    "periodicity": "ONE_TIME"  # For one-time purchases
                }
                
                # Add webhook URL if available (this is not in the schema but might be accepted)
                if webhook_url:
                    invoice_data["hookUrl"] = webhook_url
                
                # Use correct Lava.top v2 API endpoint from Swagger documentation
                url = f"{self.api_url}/api/v2/invoice"
                
                logger.info(f"Creating invoice via Lava.top v2 API: {url}")
                logger.debug(f"Invoice data: {json.dumps(invoice_data)}")
                
                # Make API request with proper authentication
                headers = {
                    "Content-Type": "application/json",
                    "X-Api-Key": self.api_key  # Required authentication header
                }
                
                async with aiohttp.ClientSession() as client_session:
                    try:
                        async with client_session.post(
                            url,
                            json=invoice_data,
                            timeout=aiohttp.ClientTimeout(total=30),
                            headers=headers
                        ) as response:
                            response_text = await response.text()
                            
                            logger.info(f"Lava.top v2 API Response {response.status}: {response_text[:500]}...")
                            
                            # Log transaction
                            transaction = PaymentTransaction.create_transaction(
                                payment_id=payment.id,
                                transaction_type="create_invoice",
                                status="success" if response.status == 201 else "error",  # API returns 201 on success
                                message=f"HTTP {response.status}",
                                lava_response=response_text,
                                http_status=response.status
                            )
                            session.add(transaction)
                            
                            if response.status == 201:  # Swagger shows 201 for successful creation
                                try:
                                    response_data = await response.json()
                                    
                                    # Extract payment data based on InvoicePaymentParamsResponse schema
                                    payment.lava_invoice_id = response_data.get("id")
                                    payment.lava_payment_url = response_data.get("paymentUrl")
                                    
                                    # Store the order ID for tracking (our internal ID)
                                    payment.lava_order_id = order_id
                                    
                                    await session.commit()
                                    
                                    logger.info(f"Successfully created invoice for chat_id={chat_id}, order_id={order_id}, currency={currency.upper()}, amount={amount}")
                                    return True, f"Счёт создан успешно ({currency.upper()}: {amount})", payment
                                        
                                except Exception as json_error:
                                    logger.error(f"JSON parse error: {json_error}")
                                    payment.mark_as_failed()
                                    await session.commit()
                                    return False, "Ошибка обработки ответа от платёжной системы", None
                            else:
                                # Handle error response
                                try:
                                    error_data = await response.json()
                                    error_msg = error_data.get("error", f"HTTP {response.status}")
                                except:
                                    error_msg = f"HTTP {response.status}: {response_text}"
                                
                                logger.error(f"Lava.top v2 API error: {error_msg}")
                                payment.mark_as_failed()
                                await session.commit()
                                return False, f"Ошибка создания платежа: {error_msg}", None
                                    
                    except Exception as request_error:
                        logger.error(f"Request error: {request_error}")
                        payment.mark_as_failed()
                        await session.commit()
                        return False, f"Ошибка подключения к платёжной системе: {str(request_error)}", None
                    
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating invoice with currency: {e}")
                return False, "Внутренняя ошибка сервера", None
            break  # Exit the async for loop 
    
    def get_offer_id(self, package_id: str, currency: str) -> str:
        """
        Get Offer ID for package and currency.
        
        Args:
            package_id: Package ID (100, 200, 300)
            currency: Currency code (RUB, EUR, USD)
            
        Returns:
            Offer ID (UUID) or None if not found
        """
        offer_id = self.offer_mapping.get(package_id, {}).get(currency.upper())
        
        if not offer_id:
            logger.warning(f"No offer ID found for {package_id} tokens in {currency.upper()}")
            return None
        
        logger.debug(f"Found offer ID for {package_id} tokens {currency.upper()}: {offer_id}")
        return offer_id
    
    def should_use_test_mode(self, package_id: str, currency: str) -> bool:
        """
        Determine if we should use test mode.
        
        Returns True if:
        1. DEBUG=true in environment, OR
        2. No real offer ID is available for this package/currency
        """
        if self.test_mode:
            return True
            
        offer_id = self.get_offer_id(package_id, currency)
        if not offer_id:
            logger.info(f"Using test mode because no offer ID available for {package_id} tokens in {currency}")
            return True
            
        return False
    
    async def refresh_offers(self) -> bool:
        """
        Manually refresh offers from Lava.top API.
        
        Returns:
            bool: True if offers refreshed successfully, False otherwise
        """
        logger.info("Manually refreshing offers from Lava.top API...")
        return await self._load_offers_from_api() 