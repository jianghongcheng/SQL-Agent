"""Benchmark uses the same bounded thinking adapter as the local service."""
from contractsql.planner import OllamaPlannerModel
OPTIONS={'temperature':0.6,'top_p':0.95,'top_k':20,'min_p':0,'num_predict':8192,'num_ctx':16384}
class QualityModel(OllamaPlannerModel):
    def __init__(self,model='qwen3:14b',seed=917):
        super().__init__('http://127.0.0.1:11434',model,timeout=120,max_tokens=8192,
                         json_mode=False,thinking=True,seed=seed)
