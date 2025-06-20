"""Bot handlers for Phase 2: Core Bot Logic with age-gate, loans, and basic commands."""

import logging
from typing import Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from app.config.prompts import SYSTEM_MESSAGES, COMMAND_DESCRIPTIONS, INTERFACE_MESSAGES, PAYMENT_METHODS, INTERFACE_BUTTONS
from app.database.connection import get_database
from app.services.user_service import UserService
from app.services.message_service import MessageService
from app.services.rate_limiter import rate_limiter
from app.config.settings import settings
import re

logger = logging.getLogger(__name__)


def format_actions_for_telegram(text: str) -> str:
    """Format action text by making *action* bold and italic for Telegram."""
    # Replace *action* with <b><i>action</i></b>
    return re.sub(r'\*([^*]+)\*', r'<b><i>\1</i></b>', text)


def personalize_message(message: str, user_profile) -> str:
    """Replace {{user}} placeholder with user's name from Telegram data.
    
    Args:
        message: Message text that may contain {{user}} placeholder
        user_profile: UserProfile object with Telegram user data
        
    Returns:
        Personalized message with {{user}} replaced by actual name
    """
    if not user_profile or "{{user}}" not in message:
        return message
    
    # Get user's display name: first_name if available, otherwise username
    user_name = user_profile.first_name if user_profile.first_name else (
        user_profile.username if user_profile.username else "дорогой"
    )
    
    # Replace {{user}} with the actual name
    return message.replace("{{user}}", user_name)


class BotHandlers:
    """Main bot handlers implementing Phase 2 features."""
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command with age-gate."""
        chat_id = update.effective_chat.id
        telegram_user = update.effective_user
        
        # Get or create user with Telegram data
        user = await UserService.get_or_create_user(telegram_user, chat_id)
        
        # Check if user is already age-verified
        if user.age_verified:
            await update.message.reply_text(
                SYSTEM_MESSAGES["welcome"],
                parse_mode="HTML"
            )
            return
        
        # Show age-gate inline keyboard
        keyboard = [
            [
                InlineKeyboardButton(INTERFACE_BUTTONS["age_verify_yes"], callback_data="age_verify_yes"),
                InlineKeyboardButton(INTERFACE_BUTTONS["age_verify_no"], callback_data="age_verify_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            SYSTEM_MESSAGES["age_gate"],
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    
    @staticmethod
    async def age_verification_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle age verification callback."""
        query = update.callback_query
        await query.answer()
        
        chat_id = update.effective_chat.id
        
        if query.data == "age_verify_yes":
            success = await UserService.verify_user_age(chat_id)
            if success:
                await query.edit_message_text(
                    text=SYSTEM_MESSAGES["welcome"],
                    parse_mode="HTML"
                )
                logger.info(f"User {chat_id} passed age verification")
            else:
                await query.edit_message_text(
                    text=SYSTEM_MESSAGES["error_occurred"],
                    parse_mode="HTML"
                )
        
        elif query.data == "age_verify_no":
            await query.edit_message_text(
                text=SYSTEM_MESSAGES["age_verification_failed"],
                parse_mode="HTML"
            )
            logger.info(f"User {chat_id} failed age verification")
    
    @staticmethod
    async def loans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /loans command - show current balance."""
        chat_id = update.effective_chat.id
        telegram_user = update.effective_user
        
        # Get or create user
        user = await UserService.get_or_create_user(telegram_user, chat_id)
        
        # Check age verification first
        if not user.age_verified:
            await update.message.reply_text(SYSTEM_MESSAGES["age_verification_required"])
            return
        
        if user.loan_balance > 0:
            message = INTERFACE_MESSAGES["loans_balance"].format(balance=user.loan_balance)
        else:
            message = SYSTEM_MESSAGES["no_loans"]
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    @staticmethod
    async def topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /topup command - show payment options (placeholder)."""
        chat_id = update.effective_chat.id
        
        # Age verification check
        user = await UserService.get_user_by_chat_id(chat_id)
        if not user or not user.age_verified:
            await update.message.reply_text(SYSTEM_MESSAGES["age_verification_required"])
            return
            
        # Placeholder payment buttons
        keyboard = [
            [InlineKeyboardButton(INTERFACE_BUTTONS["topup_uah"], callback_data="topup_uah")],
            [InlineKeyboardButton(INTERFACE_BUTTONS["topup_rub"], callback_data="topup_rub")],
            [InlineKeyboardButton(INTERFACE_BUTTONS["topup_try"], callback_data="topup_try")],
            [InlineKeyboardButton(INTERFACE_BUTTONS["topup_crypto"], callback_data="topup_crypto")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            INTERFACE_MESSAGES["topup_options"],
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    @staticmethod
    async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle payment method selection (placeholder)."""
        query = update.callback_query
        await query.answer()
        
        method = PAYMENT_METHODS.get(query.data, SYSTEM_MESSAGES["unknown_payment_method"])
        
        await query.edit_message_text(
            INTERFACE_MESSAGES["payment_coming_soon"].format(method=method),
            parse_mode="Markdown"
        )
    
    @staticmethod
    async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command - clear chat history."""
        chat_id = update.effective_chat.id
        
        # Age verification check
        user = await UserService.get_user_by_chat_id(chat_id)
        if not user or not user.age_verified:
            await update.message.reply_text(SYSTEM_MESSAGES["age_verification_required"])
            return
        
        await UserService.reset_chat_history(chat_id)
        await update.message.reply_text(
            SYSTEM_MESSAGES["reset_confirm"],
            parse_mode="HTML"
        )
    
    @staticmethod
    async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command - show and edit preferences."""
        chat_id = update.effective_chat.id
        telegram_user = update.effective_user
        
        # Get or create user
        user = await UserService.get_or_create_user(telegram_user, chat_id)
        
        if not user.age_verified:
            await update.message.reply_text(SYSTEM_MESSAGES["age_verification_required"])
            return
        
        # Get current preference
        current_preference = await UserService.get_current_preference(chat_id)
        
        # Create profile display with interactive buttons
        if current_preference and current_preference.strip():
            prefs_text = current_preference[:200] + "..." if len(current_preference) > 200 else current_preference
            message = INTERFACE_MESSAGES["profile_with_preferences"].format(
                balance=user.loan_balance,
                preferences=prefs_text
            )
        else:
            message = INTERFACE_MESSAGES["profile_no_preferences"].format(balance=user.loan_balance)
        
        # Add interactive buttons
        keyboard = [
            [InlineKeyboardButton(INTERFACE_BUTTONS["edit_preferences"], callback_data="edit_preferences")],
            [InlineKeyboardButton(INTERFACE_BUTTONS["view_full_preferences"], callback_data="view_full_preferences")],
            [InlineKeyboardButton(INTERFACE_BUTTONS["clear_preferences"], callback_data="clear_preferences")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode="Markdown")
    
    @staticmethod
    async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /about command - usage tips."""
        await update.message.reply_text(INTERFACE_MESSAGES["about_text"], parse_mode="Markdown")
    
    @staticmethod
    async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command - check AI service status (debug only)."""
        # Only allow in development mode
        if not settings.debug:
            await update.message.reply_text(SYSTEM_MESSAGES["debug_command_disabled"])
            return
        
        try:
            from app.services.ai_service import ai_service
            health_status = await ai_service.health_check()
            
            status_text = INTERFACE_MESSAGES["health_check_status"].format(
                initialized=health_status['initialized'],
                tokenizer_loaded=health_status['tokenizer_loaded'],
                client_ready=health_status['client_ready'],
                api_responsive=health_status.get('api_responsive', SYSTEM_MESSAGES["api_status_unknown"]),
                timestamp=health_status['timestamp']
            )
            
            if 'error' in health_status:
                status_text += INTERFACE_MESSAGES["health_check_error"].format(error=health_status['error'])
            
            await update.message.reply_text(status_text, parse_mode='Markdown')
            
        except Exception as e:
            await update.message.reply_text(SYSTEM_MESSAGES["health_check_failed"].format(error=str(e)))
    
    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle regular user messages - core Phase 2 logic."""
        # Input validation
        if not update or not update.effective_chat or not update.message:
            logger.error("Invalid update received in handle_message")
            return
            
        chat_id = update.effective_chat.id
        user_message = update.message.text
        
        # Validate message content
        if not user_message or not user_message.strip():
            await update.message.reply_text(
                "Please send me a text message! 😊",
                parse_mode="HTML"
            )
            return
            
        # Check message length (prevent abuse)
        if len(user_message) > 4000:
            await update.message.reply_text(
                "Whoa there! That message is way too long! 😅 Try keeping it under 4000 characters, babe! 💕",
                parse_mode="HTML"
            )
            return
        
        # Check if we're in preferences editing mode first
        if context.user_data.get("editing_preferences", False):
            handled = await BotHandlers.handle_preferences_edit(update, context)
            if handled:
                return
        
        # Rate limiting check
        if await rate_limiter.is_rate_limited(chat_id):
            remaining = await rate_limiter.get_remaining_time(chat_id)
            await update.message.reply_text(
                f"{SYSTEM_MESSAGES['rate_limit']} {SYSTEM_MESSAGES['rate_limit_retry'].format(remaining=remaining)}",
                parse_mode="HTML"
            )
            return
        
        # Age verification check
        user = await UserService.get_user_by_chat_id(chat_id)
        if not user or not user.age_verified:
            await update.message.reply_text(SYSTEM_MESSAGES["age_verification_required"])
            return
        
        # Loan balance check
        if not await UserService.deduct_loan(chat_id):
            # Create topup button
            keyboard = [[InlineKeyboardButton(INTERFACE_BUTTONS["topup_credits"], callback_data="show_topup")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                SYSTEM_MESSAGES["no_loans"],
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        
        # Save user message and generate AI response
        async for db in get_database():
            message_service = MessageService(db)
            
            # Save user message
            await message_service.save_user_message(chat_id, user_message)
            
            # Increment user's total message count
            await UserService.increment_user_message_count(chat_id)
            
            # Show "typing" status while generating response
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Generate AI response
            try:
                ai_response = await message_service.generate_ai_response(user_message, chat_id)
                
                # Get user profile for personalization
                user_profile = await UserService.get_user_by_chat_id(chat_id)
                
                # Personalize the response (replace {{user}} with actual name)
                personalized_response = personalize_message(ai_response, user_profile)
                
                # Save AI response
                await message_service.save_assistant_message(chat_id, personalized_response)
                
                # Format actions for Telegram (convert *action* to bold+italic)
                formatted_response = format_actions_for_telegram(personalized_response)
                
                # Send response to user
                await update.message.reply_text(
                    formatted_response,
                    parse_mode="HTML"
                )
                
                logger.info(f"Successfully processed message for chat {chat_id}")
                
            except Exception as e:
                logger.error(f"Error processing message for chat {chat_id}: {e}")
                
                # Fallback response in case of any error
                await update.message.reply_text(
                    SYSTEM_MESSAGES["fallback_error"],
                    parse_mode="HTML"
                )

    @staticmethod
    async def preferences_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle preferences management callbacks."""
        query = update.callback_query
        await query.answer()
        
        chat_id = update.effective_chat.id
        
        if query.data == "edit_preferences":
            # Store state for next message
            context.user_data["editing_preferences"] = True
            
            await query.edit_message_text(
                INTERFACE_MESSAGES["edit_preferences_prompt"],
                parse_mode="Markdown"
            )
            
        elif query.data == "view_full_preferences":
            preferences = await UserService.get_current_preference(chat_id)
            
            if preferences and preferences.strip():
                # Add back button
                keyboard = [[InlineKeyboardButton(INTERFACE_BUTTONS["back_to_profile"], callback_data="back_to_profile")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    INTERFACE_MESSAGES["view_full_preferences"].format(preferences=preferences),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    INTERFACE_MESSAGES["no_preferences_set"],
                    parse_mode="Markdown"
                )
                
        elif query.data == "clear_preferences":
            # Confirmation dialog
            keyboard = [
                [
                    InlineKeyboardButton(INTERFACE_BUTTONS["confirm_clear"], callback_data="confirm_clear_preferences"),
                    InlineKeyboardButton(INTERFACE_BUTTONS["cancel"], callback_data="back_to_profile")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                INTERFACE_MESSAGES["clear_preferences_confirm"],
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
        elif query.data == "confirm_clear_preferences":
            await UserService.clear_user_preference(chat_id)
            
            await query.edit_message_text(
                INTERFACE_MESSAGES["preferences_cleared"],
                parse_mode="Markdown"
            )
            
        elif query.data == "back_to_profile":
            # Show profile directly via callback query
            preferences = await UserService.get_current_preference(chat_id)
            user = await UserService.get_user_by_chat_id(chat_id)
            
            # Create profile display with interactive buttons
            if preferences and preferences.strip():
                prefs_text = preferences[:200] + "..." if len(preferences) > 200 else preferences
                message = INTERFACE_MESSAGES["profile_with_preferences"].format(
                    balance=user.loan_balance if user else 0,
                    preferences=prefs_text
                )
            else:
                message = INTERFACE_MESSAGES["profile_no_preferences"].format(balance=user.loan_balance if user else 0)
            
            # Add interactive buttons
            keyboard = [
                [InlineKeyboardButton(INTERFACE_BUTTONS["edit_preferences"], callback_data="edit_preferences")],
                [InlineKeyboardButton(INTERFACE_BUTTONS["view_full_preferences"], callback_data="view_full_preferences")],
                [InlineKeyboardButton(INTERFACE_BUTTONS["clear_preferences"], callback_data="clear_preferences")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    @staticmethod
    async def handle_preferences_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle preferences editing when user sends new preferences."""
        chat_id = update.effective_chat.id
        user_message = update.message.text
        
        # Check if we're in preferences editing mode
        if not context.user_data.get("editing_preferences", False):
            return False  # Not handling this message
        
        # Clear the editing state
        context.user_data["editing_preferences"] = False
        
        # Update preferences
        await UserService.update_user_preference(chat_id, user_message, "user_edit")
        
        # Show simple confirmation message as requested
        await update.message.reply_text(
            SYSTEM_MESSAGES["profile_updated"],
            parse_mode="HTML"
        )
        
        logger.info(f"Updated preferences for user {chat_id}")
        return True  # Message was handled


def setup_handlers(application) -> None:
    """Set up all bot handlers."""
    # Command handlers
    application.add_handler(CommandHandler("start", BotHandlers.start_command))
    application.add_handler(CommandHandler("loans", BotHandlers.loans_command))
    application.add_handler(CommandHandler("topup", BotHandlers.topup_command))
    application.add_handler(CommandHandler("reset", BotHandlers.reset_command))
    application.add_handler(CommandHandler("profile", BotHandlers.profile_command))
    application.add_handler(CommandHandler("about", BotHandlers.about_command))
    application.add_handler(CommandHandler("help", BotHandlers.about_command))  # Alias
    application.add_handler(CommandHandler("health", BotHandlers.health_command))  # Debug only
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(
        BotHandlers.age_verification_callback,
        pattern="^age_verify_"
    ))
    application.add_handler(CallbackQueryHandler(
        BotHandlers.payment_callback,
        pattern="^topup_"
    ))
    application.add_handler(CallbackQueryHandler(
        BotHandlers.topup_command,
        pattern="^show_topup$"
    ))
    application.add_handler(CallbackQueryHandler(
        BotHandlers.preferences_callback,
        pattern="^(edit_preferences|view_full_preferences|clear_preferences|confirm_clear_preferences|back_to_profile)$"
    ))
    
    # Message handler for regular chat
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        BotHandlers.handle_message
    ))
    
    logger.info("All bot handlers registered") 