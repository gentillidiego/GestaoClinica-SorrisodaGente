"""
Serviço centralizado para invalidação de cache.
"""
from extensions import cache

class CacheService:
    STUDENTS_KEY = 'students_list'
    
    @staticmethod
    def invalidate_students():
        cache.delete(CacheService.STUDENTS_KEY)
    
    @staticmethod
    def invalidate_patient(patient_id):
        cache.delete(f'patient_{patient_id}')
