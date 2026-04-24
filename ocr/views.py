from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from deals.models import Deal, DealDocument
import pytesseract
from PIL import Image
import json
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

@api_view(['POST'])
def upload_document(request):
    deal_id = request.data.get('deal_id')
    file = request.FILES.get('file')
    document_type = request.data.get('document_type', 'other')

    if not deal_id or not file:
        return Response({'error': 'deal_id and file are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        deal = Deal.objects.get(id=deal_id)
    except Deal.DoesNotExist:
        return Response({'error': 'Deal not found'}, status=status.HTTP_404_NOT_FOUND)

    # Save file temporarily
    file_name = default_storage.save('temp/' + file.name, ContentFile(file.read()))
    file_path = default_storage.path(file_name)

    # Perform OCR
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        # For simplicity, assume text contains key-value pairs or parse it
        # Here, we'll just store the text
        ocr_data = {'extracted_text': text}
    except Exception as e:
        ocr_data = {'error': str(e)}
    finally:
        # Clean up temp file
        os.remove(file_path)

    # Create DealDocument
    deal_document = DealDocument.objects.create(
        deal=deal,
        document_type=document_type,
        file=file,  # This will save to deal_documents/
        ocr_response=ocr_data,
        ocr_status=True if 'error' not in ocr_data else False,
    )

    # Optionally update Deal with extracted info
    # For example, if text contains 'Emirates ID: 123', parse and update
    # But for now, skip or add simple logic

    return Response({'message': 'Document processed and saved', 'deal_document_id': deal_document.id}, status=status.HTTP_201_CREATED)
