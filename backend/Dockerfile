FROM python:3.14-slim

WORKDIR /app

# Copy requirements from the root context
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/backend/

# Copy required artifacts and data
# (Ensuring git LFS files like feature_lookup.pkl, graph_index.pkl, learned_model.joblib are present)
COPY artifacts/ /app/artifacts/
COPY data/ /app/data/

# Set Python path so `backend.ledgr` can be resolved
ENV PYTHONPATH=/app

# Expose the default port required by Hugging Face Spaces
EXPOSE 7860

# Start the uvicorn server without --reload
CMD ["uvicorn", "ledgr.service:app", "--host", "0.0.0.0", "--port", "7860"]
