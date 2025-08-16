"""
File processing service for document conversion and handling
"""

import io
import uuid
import logging
from pathlib import Path
from typing import List
from PIL import Image
from pdf2image import convert_from_bytes
from fastapi import UploadFile

from models.document import ProcessedFile
from services.s3_service import upload_to_s3

logger = logging.getLogger(__name__)

def get_file_type(filename: str) -> str:
    """Get file type from filename extension"""
    return Path(filename).suffix.lower().lstrip('.')

def is_supported_file_type(filename: str) -> bool:
    """Check if file type is supported for processing"""
    file_type = get_file_type(filename)
    return file_type in ['jpg', 'jpeg', 'png', 'tiff', 'tif', 'pdf']

def convert_tiff_to_png(tiff_data: bytes) -> bytes:
    """Convert TIFF data to PNG format with high quality"""
    try:
        with Image.open(io.BytesIO(tiff_data)) as img:
            # Convert to RGB if necessary (for TIFF with alpha channel)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Save as PNG with high quality
            png_buffer = io.BytesIO()
            img.save(png_buffer, format='PNG', optimize=False, compress_level=1)
            return png_buffer.getvalue()
    except Exception as e:
        logger.error(f"Failed to convert TIFF to PNG: {e}")
        raise

def convert_pdf_to_pngs(pdf_data: bytes) -> List[bytes]:
    """Convert PDF to list of PNG images (one per page) with high quality"""
    try:
        # Convert PDF to images with high DPI for quality
        # Try default first, then with explicit poppler path if needed
        try:
            images = convert_from_bytes(
                pdf_data,
                dpi=300,  # High DPI for quality
                fmt='PNG',
                thread_count=1
            )
        except Exception as poppler_error:
            # Try with explicit poppler path (common Docker/Linux locations)
            poppler_paths = ['/usr/bin', '/usr/local/bin', '/opt/homebrew/bin']
            for poppler_path in poppler_paths:
                try:
                    images = convert_from_bytes(
                        pdf_data,
                        dpi=300,
                        fmt='PNG', 
                        thread_count=1,
                        poppler_path=poppler_path
                    )
                    break
                except:
                    continue
            else:
                # If all paths fail, raise the original error
                raise poppler_error
        
        png_list = []
        for img in images:
            # Convert PIL Image to bytes
            png_buffer = io.BytesIO()
            img.save(png_buffer, format='PNG', optimize=False, compress_level=1)
            png_list.append(png_buffer.getvalue())
        
        return png_list
    except Exception as e:
        logger.error(f"Failed to convert PDF to PNG: {e}")
        raise

async def process_uploaded_file(
    file: UploadFile, 
    case_id: str
) -> List[ProcessedFile]:
    """Process uploaded file and return list of processed files"""
    try:
        # Read file data
        file_data = await file.read()
        original_filename = file.filename
        file_type = get_file_type(original_filename)
        
        processed_files = []
        
        if file_type in ['jpg', 'jpeg']:
            # Keep as JPG
            s3_key = f"documents/{case_id}/{uuid.uuid4().hex[:8]}_{original_filename}"
            s3_location = await upload_to_s3(file_data, s3_key, "image/jpeg")
            
            processed_files.append(ProcessedFile(
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type="jpg",
                file_size=len(file_data),
                s3_location=s3_location,
                s3_key=s3_key
            ))
            
        elif file_type == 'png':
            # Keep as PNG
            s3_key = f"documents/{case_id}/{uuid.uuid4().hex[:8]}_{original_filename}"
            s3_location = await upload_to_s3(file_data, s3_key, "image/png")
            
            processed_files.append(ProcessedFile(
                original_filename=original_filename,
                processed_filename=original_filename,
                file_type="png",
                file_size=len(file_data),
                s3_location=s3_location,
                s3_key=s3_key
            ))
            
        elif file_type in ['tiff', 'tif']:
            # Convert TIFF to PNG
            png_data = convert_tiff_to_png(file_data)
            png_filename = f"{Path(original_filename).stem}.png"
            s3_key = f"documents/{case_id}/{uuid.uuid4().hex[:8]}_{png_filename}"
            s3_location = await upload_to_s3(png_data, s3_key, "image/png")
            
            processed_files.append(ProcessedFile(
                original_filename=original_filename,
                processed_filename=png_filename,
                file_type="png",
                file_size=len(png_data),
                s3_location=s3_location,
                s3_key=s3_key
            ))
            
        elif file_type == 'pdf':
            # Convert PDF to multiple PNGs (one per page)
            png_list = convert_pdf_to_pngs(file_data)
            base_filename = Path(original_filename).stem
            
            for page_num, png_data in enumerate(png_list, 1):
                png_filename = f"{base_filename}_page_{page_num}.png"
                s3_key = f"documents/{case_id}/{uuid.uuid4().hex[:8]}_{png_filename}"
                s3_location = await upload_to_s3(png_data, s3_key, "image/png")
                
                processed_files.append(ProcessedFile(
                    original_filename=original_filename,
                    processed_filename=png_filename,
                    file_type="png",
                    file_size=len(png_data),
                    s3_location=s3_location,
                    s3_key=s3_key,
                    page_number=page_num
                ))
        
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return processed_files
        
    except Exception as e:
        logger.error(f"Failed to process file {original_filename}: {e}")
        raise