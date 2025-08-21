# ===== Arquivo: services/analyze_service.py =====

from utils.advanced_data_analyst import AdvancedDataAnalyst

class AnalyzeService:
    # Reutilizar o analista (igual st.cache_resource)
    analyst = AdvancedDataAnalyst()

    @classmethod
    def run_analysis(cls, request):
        try:
            payload = request.model_dump()
        except AttributeError:
            payload = request.dict()
        return cls.analyst.run_analysis(payload)
