import asyncio
from info import *
from pyrogram import Client
from Lucia.util.config_parser import TokenParser
from . import multi_clients, work_loads, SilentX
from logging_helper import LOGGER

async def initialize_clients():
    """Initialize multiple Telegram bot clients for load balancing."""
    # Initialize default client
    multi_clients[0] = SilentX
    work_loads[0] = 0
    
    # Parse tokens from environment
    all_tokens = TokenParser().parse_from_env()
    if not all_tokens:
        LOGGER.info("No additional clients found, using default client")
        return
    
    async def start_client(client_id, token):
        """Start a single client with error handling."""
        try:
            LOGGER.info(f"Starting Client {client_id}")
            
            # Add delay for the last client to prevent API rate limits
            if client_id == len(all_tokens):
                await asyncio.sleep(2)
                LOGGER.info("Starting final client, this may take some time...")
            
            client = Client(
                name=f"client_{client_id}",  # More descriptive naming
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=token,
                sleep_threshold=SLEEP_THRESHOLD,
                no_updates=True,
                in_memory=True
            )
            
            # Start the client
            await client.start()
            
            # Initialize workload counter
            work_loads[client_id] = 0
            
            LOGGER.info(f"Successfully started Client {client_id}")
            return client_id, client
            
        except Exception as e:
            LOGGER.error(f"Failed to start Client {client_id}: {str(e)}", exc_info=True)
            return client_id, None  # Return None for failed clients
    
    # Start all clients concurrently
    LOGGER.info(f"Initializing {len(all_tokens)} additional clients...")
    
    try:
        results = await asyncio.gather(
            *[start_client(i, token) for i, token in all_tokens.items()],
            return_exceptions=True
        )
        
        # Filter out failed clients and update multi_clients
        successful_clients = {}
        failed_count = 0
        
        for result in results:
            if isinstance(result, Exception):
                LOGGER.error(f"Client initialization failed with exception: {result}")
                failed_count += 1
                continue
                
            client_id, client = result
            if client is not None:
                successful_clients[client_id] = client
            else:
                failed_count += 1
        
        # Update the global multi_clients dictionary
        multi_clients.update(successful_clients)
        
        # Log results
        total_clients = len(multi_clients)
        if total_clients > 1:
            LOGGER.info(f"Multi-Client Mode Enabled - {total_clients} clients active")
            if failed_count > 0:
                LOGGER.warning(f"{failed_count} clients failed to initialize")
        else:
            LOGGER.info("No additional clients were initialized, using default client only")
            
    except Exception as e:
        LOGGER.error(f"Critical error during client initialization: {e}", exc_info=True)
        LOGGER.info("Falling back to default client only")

async def get_least_loaded_client():
    """Get the client with the lowest workload for load balancing."""
    if not multi_clients:
        raise RuntimeError("No clients available")
    
    # Find client with minimum workload
    min_client_id = min(work_loads.keys(), key=lambda k: work_loads[k])
    return multi_clients[min_client_id], min_client_id

async def increment_workload(client_id):
    """Increment workload for a specific client."""
    if client_id in work_loads:
        work_loads[client_id] += 1

async def decrement_workload(client_id):
    """Decrement workload for a specific client."""
    if client_id in work_loads and work_loads[client_id] > 0:
        work_loads[client_id] -= 1

async def shutdown_clients():
    """Gracefully shutdown all clients."""
    LOGGER.info("Shutting down all clients...")
    
    shutdown_tasks = []
    for client_id, client in multi_clients.items():
        if hasattr(client, 'stop') and client_id != 0:  # Don't shutdown default client
            shutdown_tasks.append(client.stop())
    
    if shutdown_tasks:
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
    
    LOGGER.info("All clients shut down successfully")
