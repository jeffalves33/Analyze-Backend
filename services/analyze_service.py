# ===== Arquivo: services/analyze_service.py =====

from utils.advanced_data_analyst import AdvancedDataAnalyst

class AnalyzeService:
    # Reutilizar o analista (igual st.cache_resource)
    analyst = AdvancedDataAnalyst()

    @classmethod
    def run_analysis(cls, request):
        return cls.analyst.run_analysis(
            client_id=request.client_id,
            platforms=request.platforms,
            analysis_type=request.analysis_type,
            start_date=request.start_date,
            end_date=request.end_date,
            output_format=request.output_format,
            custom_query=request.custom_query
        )
