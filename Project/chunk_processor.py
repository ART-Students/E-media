import zlib
import struct
import os
from chunk import Chunk
from pathlib import Path
import math

from PIL.Image import new

from keys import Keys
from rsa import RSA
from critical_chunks_data import IHDRData, IDATFilter, PLTEData
from ancillary_chunks_data import (
    gAMAData, cHRMData, sRGBData, tEXtData, iTXtData, zTXtData, tIMEData
)


class PNGChunkProcessor:

    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
    CRITICAL_CHUNKS = [b'IHDR', b'PLTE', b'IDAT', b'IEND']


    def __init__(self):
        self.chunks = []
        self.encrypt_data = bytearray()
        self.after_iend_data = bytearray()
        self.decrypt_data = bytearray()
        self.encrypt_data_from_library = bytearray()
        self.after_iend_data__from_library = bytearray()


    @staticmethod
    def validate_png(img):
        if (img.read(len(PNGChunkProcessor.PNG_SIGNATURE))
                                        != PNGChunkProcessor.PNG_SIGNATURE):
            raise Exception('Invalid PNG Signature')


    def save_chunks(self, img):
        self.validate_png(img)
        while True:
            new_chunk = Chunk(img)
            self.chunks.append(new_chunk)
            if new_chunk.chunk_type == b'IEND':
                break


    def print_chunks_types(self):
        print([chunk.chunk_type for chunk in self.chunks])


    def IHDR_chunk_processor(self):
        IHDR_data = self.chunks[0].chunk_data
        IHDR_data_values = struct.unpack('>IIBBBBB', IHDR_data)
        IHDR_data = IHDRData(IHDR_data_values)
        self.width = IHDR_data.get_width()
        self.height = IHDR_data.get_height()
        self.color_type = IHDR_data.get_color_type()
        self.bit_depth = IHDR_data.get_bit_depth()
        IHDR_data.print_IHDR_data()


    def IDAT_chunk_processor_ecb(self):
        IDAT_data = b''.join(chunk.chunk_data for chunk in self.chunks
                                            if chunk.chunk_type == b'IDAT')
        IDAT_data = zlib.decompress(IDAT_data)
        IDAT_filter = IDATFilter(self.width, self.height, IDAT_data)
        information = IDAT_filter.print_recon_pixels()
        print(information)
        keys = Keys(512)
        public_key = keys.generate_public_key()
        private_key = keys.generate_private_key()
        rsa = RSA(public_key, private_key)
        self.encrypt_data, self.after_iend_data = rsa.ecb_encrypt(IDAT_data)
        self.decrypt_data = rsa.ecb_decrypt(self.encrypt_data, self.after_iend_data)
        self.encrypt_data_from_library, self.after_iend_data__from_library = rsa.crypto_library_encrypt(IDAT_data)

    def IDAT_chunk_processor_cbc(self):
        IDAT_data = b''.join(chunk.chunk_data for chunk in self.chunks
                                            if chunk.chunk_type == b'IDAT')
        IDAT_data = zlib.decompress(IDAT_data)
        IDAT_filter = IDATFilter(self.width, self.height, IDAT_data)
        information = IDAT_filter.print_recon_pixels()
        print(information)
        keys = Keys(512)
        public_key = keys.generate_public_key()
        private_key = keys.generate_private_key()
        rsa = RSA(public_key, private_key)
        self.encrypt_data, self.after_iend_data = rsa.cbc_encrypt(IDAT_data)
        self.decrypt_data = rsa.cbc_decrypt(self.encrypt_data, self.after_iend_data)


    def PLTE_chunk_processor(self):
        PLTE_chunk = []
        i = 0

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_chunk.append(chunk)
                PLTE_index = i
            i+=1
        try:
            PLTE_chunk is None
        except ValueError:
            raise Exception("Image not have PLTE chunk")

        if self.color_type == 2 or self.color_type == 6:
            print("\nPLTE chunk is optional")
        elif self.color_type == 3:
            print("\nPLTE chunk must appear")

        try:
            len(PLTE_chunk) != 1
        except ValueError:
            raise Exception("Incorrect number of PLTE chunk")

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_length= self.chunks[PLTE_index].get_chunk_length()
                try:
                    PLTE_length % 3 != 0
                except ValueError:
                    raise Exception("Incorrect PLTE length - not divisible \
                                                                        by 3")

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_data = PLTEData(PLTE_chunk[0].chunk_data)
                PLTE_data.parse_plte_data()
                PLTE_data.print_palette()
                PLTE_data.show_palette()
                try:
                    PLTE_data.get_amount_of_entries_in_palette() > 2**self.bit_depth
                except ValueError:
                    raise Exception("Incorrect number of entries in palette!")


    def tIME_chunk_prcessor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'tIME':
                index = self.chunks.index(chunk)
                tIME_data = self.chunks[index].chunk_data
                tIME_data_values = struct.unpack('>HBBBBB', tIME_data)
                tIME_data = tIMEData(tIME_data_values)
                tIME_data.print_modification_date()


    def gAMA_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'IDAT':
                IDAT_index = self.chunks.index(chunk)
                break

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_index = self.chunks.index(chunk)
            else:
                PLTE_index = math.inf

        for chunk in self.chunks:
            if chunk.chunk_type == b'gAMA':
                gAMA_index = self.chunks.index(chunk)
                try:
                    IDAT_index < gAMA_index or PLTE_index < gAMA_index
                except ValueError:
                    raise Exception("chunk gAMA must precede the first IDAT \
                                                        chunk or PLTE chunk!")
                gAMA_data = self.chunks[gAMA_index].chunk_data
                gAMA_data_values = struct.unpack('>I', gAMA_data)
                gAMA_data = gAMAData(gAMA_data_values)
                gAMA_data.print_real_gamma()


    def cHRM_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'IDAT':
                IDAT_index = self.chunks.index(chunk)
                break

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_index = self.chunks.index(chunk)
            else:
                PLTE_index = math.inf

        for chunk in self.chunks:
            if chunk.chunk_type == b'cHRM':
                cHRM_index = self.chunks.index(chunk)
                try:
                    IDAT_index < cHRM_index or PLTE_index < cHRM_index
                except ValueError:
                    raise Exception("chunk cHRM must precede the first IDAT \
                                                        chunk or PLTE chunk!")
                cHRM_data = self.chunks[cHRM_index].chunk_data
                cHRM_data_values = struct.unpack('>IIIIIIII', cHRM_data)
                cHRM_data = cHRMData(cHRM_data_values)
                cHRM_data.print_chromaticity_values()


    def sRGB_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'IDAT':
                IDAT_index = self.chunks.index(chunk)
                break

        for chunk in self.chunks:
            if chunk.chunk_type == b'PLTE':
                PLTE_index = self.chunks.index(chunk)
            else:
                PLTE_index = math.inf

        for chunk in self.chunks:
            if chunk.chunk_type == b'sRGB':
                sRGB_index = self.chunks.index(chunk)
                try:
                    IDAT_index < sRGB_index or PLTE_index < sRGB_index
                except ValueError:
                    raise Exception("chunk sRGB must precede the first IDAT \
                                                        chunk or PLTE chunk!")
                sRGB_data = self.chunks[sRGB_index].chunk_data
                sRGB_data_values = struct.unpack('>B', sRGB_data)
                sRGB_data = sRGBData(sRGB_data_values)
                sRGB_data.print_rendering_intent()


    def IEND_chunk_processor(self):
        number_of_chunks = len(self.chunks)
        if self.chunks[number_of_chunks-1].chunk_type != b"IEND":
            print("IEND must be the last chunk")
        IEND_data = struct.unpack('>',
                                self.chunks[number_of_chunks - 1].chunk_data)
        if  len(IEND_data) == 0:
            print("\nIEND:\n")
            print("IEND is empty")


    def tEXt_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'tEXt':
                data = struct.unpack('{}s'.format(len(chunk.chunk_data)),
                                                             chunk.chunk_data)
                text_chunk = tEXtData(data)
                text_chunk.decode_tEXt_data()


    def iTXt_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'iTXt':
                data = struct.unpack('{}s'.format(len(chunk.chunk_data)),
                                                             chunk.chunk_data)
                text_chunk = iTXtData(data)
                text_chunk.decode_iTXt_data()


    def zTXt_chunk_processor(self):
        for chunk in self.chunks:
            if chunk.chunk_type == b'zTXt':
                data = struct.unpack('{}s'.format(len(chunk.chunk_data)),
                                                             chunk.chunk_data)
                text_chunk = zTXtData(data)
                text_chunk.decode_zTXt_data()


    def create_new_image(self):
        filename = "tmp.png"
        img_path = "./images/{}".format(filename)
        if Path(img_path).is_file():
            os.remove(img_path)
        temporary_file = open(img_path, 'wb')
        temporary_file.write(PNGChunkProcessor.PNG_SIGNATURE)
        for chunk in self.chunks:
            if chunk.chunk_type in [b'IDAT']:
                new_data = zlib.compress(self.decrypt_data, 9)
                new_crc = zlib.crc32(new_data, zlib.crc32(struct.pack('>4s', b'IDAT')))
                chunk_len = len(new_data)
                temporary_file.write(struct.pack('>I', chunk_len))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(new_data)
                temporary_file.write(struct.pack('>I', new_crc))
            else:
                temporary_file.write(struct.pack('>I', chunk.chunk_length))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(chunk.chunk_data)
                temporary_file.write(struct.pack('>I', chunk.chunk_crc))
        temporary_file.close()
        return filename

    def create_ecb_image(self):
        filename = "ecb.png"
        img_path = "./images/{}".format(filename)
        if Path(img_path).is_file():
            os.remove(img_path)
        temporary_file = open(img_path, 'wb')
        temporary_file.write(PNGChunkProcessor.PNG_SIGNATURE)
        for chunk in self.chunks:
            if chunk.chunk_type in [b'IDAT']:
                new_data = zlib.compress(self.encrypt_data, 9)
                new_crc = zlib.crc32(new_data, zlib.crc32(struct.pack('>4s', b'IDAT')))
                chunk_len = len(new_data)
                temporary_file.write(struct.pack('>I', chunk_len))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(new_data)
                temporary_file.write(struct.pack('>I', new_crc))
            else:
                temporary_file.write(struct.pack('>I', chunk.chunk_length))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(chunk.chunk_data)
                temporary_file.write(struct.pack('>I', chunk.chunk_crc))
        temporary_file.close()
        return filename

    def create_cbc_image(self):
        filename = "cbc.png"
        img_path = "./images/{}".format(filename)
        if Path(img_path).is_file():
            os.remove(img_path)
        temporary_file = open(img_path, 'wb')
        temporary_file.write(PNGChunkProcessor.PNG_SIGNATURE)
        for chunk in self.chunks:
            if chunk.chunk_type in [b'IDAT']:
                new_data = zlib.compress(self.encrypt_data, 9)
                new_crc = zlib.crc32(new_data, zlib.crc32(struct.pack('>4s', b'IDAT')))
                chunk_len = len(new_data)
                temporary_file.write(struct.pack('>I', chunk_len))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(new_data)
                temporary_file.write(struct.pack('>I', new_crc))
            else:
                temporary_file.write(struct.pack('>I', chunk.chunk_length))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(chunk.chunk_data)
                temporary_file.write(struct.pack('>I', chunk.chunk_crc))
        temporary_file.close()
        return filename

    def create_ecb_library_image(self):
        filename = "ecb_library.png"
        img_path = "./images/{}".format(filename)
        if Path(img_path).is_file():
            os.remove(img_path)
        temporary_file = open(img_path, 'wb')
        temporary_file.write(PNGChunkProcessor.PNG_SIGNATURE)
        for chunk in self.chunks:
            if chunk.chunk_type in [b'IDAT']:
                new_data = zlib.compress(self.encrypt_data_from_library, 9)
                new_crc = zlib.crc32(new_data, zlib.crc32(struct.pack('>4s', b'IDAT')))
                chunk_len = len(new_data)
                temporary_file.write(struct.pack('>I', chunk_len))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(new_data)
                temporary_file.write(struct.pack('>I', new_crc))
            else:
                temporary_file.write(struct.pack('>I', chunk.chunk_length))
                temporary_file.write(chunk.chunk_type)
                temporary_file.write(chunk.chunk_data)
                temporary_file.write(struct.pack('>I', chunk.chunk_crc))
        temporary_file.close()
        return filename
