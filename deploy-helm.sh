#!/bin/bash

# Purdue AF Agent Helm Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
RELEASE_NAME="purdue-af-agent"
NAMESPACE="default"
DRY_RUN=false
UPGRADE=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -r, --release-name NAME    Helm release name (default: purdue-af-agent)"
    echo "  -n, --namespace NAMESPACE  Kubernetes namespace (default: default)"
    echo "  -d, --dry-run              Show what would be deployed without actually deploying"
    echo "  -u, --upgrade              Upgrade existing release"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy to default namespace"
    echo "  $0 -n production                      # Deploy to production namespace"
    echo "  $0 -d                                # Dry run to see what would be deployed"
    echo "  $0 -u                                # Upgrade existing release"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--release-name)
            RELEASE_NAME="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -u|--upgrade)
            UPGRADE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_usage
            exit 1
            ;;
    esac
done

echo -e "${GREEN}🚀 Purdue AF Agent Helm Deployment${NC}"
echo -e "${YELLOW}Release Name:${NC} $RELEASE_NAME"
echo -e "${YELLOW}Namespace:${NC} $NAMESPACE"
echo -e "${YELLOW}Dry Run:${NC} $DRY_RUN"
echo -e "${YELLOW}Upgrade:${NC} $UPGRADE"
echo ""

# Check if helm is available
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm is not installed or not in PATH${NC}"
    exit 1
fi

# Create namespace if it doesn't exist
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${YELLOW}📦 Creating namespace: $NAMESPACE${NC}"
    kubectl create namespace "$NAMESPACE"
fi

echo -e "${YELLOW}ℹ️  Using existing secret for OpenAI API key${NC}"
echo -e "${YELLOW}Make sure the secret exists in namespace $NAMESPACE${NC}"

# Build helm command
HELM_CMD="helm"
if [ "$UPGRADE" = true ]; then
    HELM_CMD="$HELM_CMD upgrade"
else
    HELM_CMD="$HELM_CMD install"
fi

HELM_CMD="$HELM_CMD $RELEASE_NAME ./helm/purdue-af-agent"
HELM_CMD="$HELM_CMD --namespace $NAMESPACE"

if [ "$DRY_RUN" = true ]; then
    HELM_CMD="$HELM_CMD --dry-run --debug"
fi

# Execute helm command
echo -e "${YELLOW}🔧 Executing: $HELM_CMD${NC}"
echo ""

if eval $HELM_CMD; then
    if [ "$DRY_RUN" = false ]; then
        echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
        echo ""
        echo -e "${YELLOW}📊 Release Status:${NC}"
        helm status "$RELEASE_NAME" --namespace "$NAMESPACE"
        echo ""
        echo -e "${YELLOW}🔍 Pod Status:${NC}"
        kubectl get pods -l app.kubernetes.io/name=purdue-af-agent -n "$NAMESPACE"
        echo ""
        echo -e "${GREEN}🎉 Purdue AF Agent is now running!${NC}"
        echo -e "${YELLOW}💡 To test the service, run:${NC}"
        echo "kubectl port-forward service/$RELEASE_NAME-service 8000:8000 -n $NAMESPACE"
        echo "curl -X POST 'http://localhost:8000/api/query' -H 'Content-Type: application/json' -d '{\"query\": \"debug pod of user test\"}'"
    else
        echo -e "${GREEN}✅ Dry run completed successfully!${NC}"
    fi
else
    echo -e "${RED}❌ Deployment failed!${NC}"
    exit 1
fi
