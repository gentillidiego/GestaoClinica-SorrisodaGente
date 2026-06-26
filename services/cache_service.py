"""
Serviço centralizado para invalidação de cache.
"""
from extensions import cache

class CacheService:
    CLINICAL_USERS_KEY = 'clinical_users_list'
    
    @staticmethod
    def invalidate_clinical_users():
        cache.delete(CacheService.CLINICAL_USERS_KEY)
    
    @staticmethod
    def invalidate_patient(patient_id):
        cache.delete(f'patient_{patient_id}')
