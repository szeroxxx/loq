#!/bin/bash

# GCP Deployment Script for Wallet Scanner
# Replace YOUR_PROJECT_ID with your actual GCP project ID

PROJECT_ID="YOUR_PROJECT_ID"
REGION="us-central1"
IMAGE_NAME="wallet-scanner"

echo "🚀 Starting GCP deployment for Wallet Scanner..."

# Step 1: Set the project
echo "📋 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable container.googleapis.com

# Step 3: Build and push Docker image
echo "🏗️ Building Docker image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$IMAGE_NAME

# Step 4: Deploy to Cloud Run (Alternative 1 - Serverless)
echo "☁️ Deploying to Cloud Run..."
gcloud run deploy $IMAGE_NAME \
    --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 3600 \
    --concurrency 1 \
    --min-instances 1 \
    --max-instances 1

echo "✅ Deployment completed!"
echo "📊 Check logs with: gcloud run logs tail $IMAGE_NAME --region $REGION"
