
# Create your views here.
from core.utils import hash_message # for hashing messages
from django.http import JsonResponse

from datetime import datetime
import asyncio

from typing import AsyncGenerator
from django.shortcuts import render, redirect
from django.http import HttpRequest, StreamingHttpResponse, HttpResponse
from . import models
import json
import random
from django.contrib.auth.decorators import login_required

@login_required
def chat(request: HttpRequest) -> HttpResponse:
    return render(request, 'chat.html')

@login_required
def create_message(request: HttpRequest) -> HttpResponse:
    content = request.POST.get("content", "").strip()
    client_hash = request.POST.get("hash")
    username = request.user.username

    # debug
    #print(f"Received content: {content}")
    #print(f"Received hash: {client_hash}")
    #print(f"Logged in user: {username}")

    if not username:
        return HttpResponse(status=403)
    author, _ = models.Author.objects.get_or_create(name=username)

    if content and client_hash:
        server_hash = hash_message(content)
        print(f"Server hash: {server_hash}")

        if server_hash != client_hash:
            return JsonResponse({"error": "Message integrity check failed."}, status=400)

        models.Message.objects.create(author=author, content=content)
        print("Message saved successfully.")
        return HttpResponse(
            json.dumps({"message": "Message saved successfully."}),
            status=201,
        )
    else:
        return JsonResponse({"error": "Content or hash is missing."}, status=400)


async def stream_chat_messages(request: HttpRequest) -> StreamingHttpResponse:
    """
    Streams chat messages to the client as we create messages.
    """
    async def event_stream():
        """
        We use this function to send a continuous stream of data 
        to the connected clients.
        """
        async for message in get_existing_messages():
            yield message

        last_id = await get_last_message_id()

        # Continuously check for new messages
        while True:
            new_messages = models.Message.objects.filter(id__gt=last_id).order_by('created_at').values(
                'id', 'author__name', 'content'
            )
            async for message in new_messages:
                yield f"data: {json.dumps(message)}\n\n"
                last_id = message['id']
            await asyncio.sleep(0.1)  # Adjust sleep time as needed to reduce db queries.

    async def get_existing_messages() -> AsyncGenerator:
        messages = models.Message.objects.all().order_by('created_at').values(
            'id', 'author__name', 'content'
        )
        async for message in messages:
            yield f"data: {json.dumps(message)}\n\n"

    async def get_last_message_id() -> int:
        last_message = await models.Message.objects.all().alast()
        return last_message.id if last_message else 0

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

