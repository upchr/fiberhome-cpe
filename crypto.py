"""
AES 加密模块

烽火 CPE 使用 AES-128-CBC 加密 API 通信：
- 密钥：sessionid 的前 16 个字符
- IV：固定值 'pqrstuvwxyz{|}~\x7f'
- 填充：PKCS7
"""

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import binascii


class AESEncryptor:
    """AES 加密器"""
    
    # 初始化向量：chr(112) 到 chr(127)
    IV = bytes(range(112, 128))  # b'pqrstuvwxyz{|}~\x7f'
    
    @classmethod
    def encrypt(cls, data: str, key: str) -> str:
        """
        加密数据
        
        Args:
            data: 要加密的字符串
            key: 密钥（sessionid 的前 16 个字符）
            
        Returns:
            十六进制编码的加密数据
        """
        if len(key) < 16:
            raise ValueError("密钥长度必须至少 16 个字符")
        
        cipher_key = key[:16].encode('utf-8')
        cipher = AES.new(cipher_key, AES.MODE_CBC, cls.IV)
        
        # PKCS7 填充并加密
        padded_data = pad(data.encode('utf-8'), AES.block_size)
        encrypted = cipher.encrypt(padded_data)
        
        # 返回十六进制字符串
        return binascii.hexlify(encrypted).decode('utf-8')
    
    @classmethod
    def decrypt(cls, hex_data: str, key: str) -> str:
        """
        解密数据
        
        Args:
            hex_data: 十六进制编码的加密数据
            key: 密钥（sessionid 的前 16 个字符）
            
        Returns:
            解密后的字符串
        """
        if len(key) < 16:
            raise ValueError("密钥长度必须至少 16 个字符")
        
        cipher_key = key[:16].encode('utf-8')
        cipher = AES.new(cipher_key, AES.MODE_CBC, cls.IV)
        
        # 解密并去除填充
        encrypted = binascii.unhexlify(hex_data)
        decrypted = cipher.decrypt(encrypted)
        unpadded = unpad(decrypted, AES.block_size)
        
        return unpadded.decode('utf-8')
