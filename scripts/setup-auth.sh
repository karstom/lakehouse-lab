#!/bin/bash

# Lakehouse Lab - Authentication Setup Wizard
# Interactive setup for federated authentication

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${PURPLE}"
    cat << 'EOF'
╔════════════════════════════════════════════════╗
║                                                ║
║        🔐 LAKEHOUSE LAB AUTH SETUP             ║
║                                                ║
║    Configure federated authentication with    ║
║         popular identity providers             ║
║                                                ║
╚════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

# Check if .env file exists
check_env_file() {
    if [[ ! -f ".env" ]]; then
        log_error "No .env file found!"
        log_info "Please run './install.sh' first to create the basic installation"
        exit 1
    fi
}

# Get current auth mode
get_current_auth_mode() {
    grep "^AUTH_MODE=" .env 2>/dev/null | cut -d'=' -f2 || echo "local_only"
}

# Show current auth status
show_current_status() {
    local current_mode=$(get_current_auth_mode)
    
    echo -e "${BLUE}📊 Current Authentication Status${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
    echo -e "Current mode: ${YELLOW}$current_mode${NC}"
    
    case "$current_mode" in
        "local_only")
            echo -e "Status: ${GREEN}✅ Local authentication only${NC}"
            echo -e "        ${BLUE}• No OAuth setup required${NC}"
            echo -e "        ${BLUE}• Uses generated credentials${NC}"
            echo -e "        ${BLUE}• Perfect for development${NC}"
            ;;
        "oauth")
            echo -e "Status: ${GREEN}✅ OAuth authentication enabled${NC}"
            show_oauth_status
            ;;
        "hybrid")
            echo -e "Status: ${GREEN}✅ Hybrid authentication (Local + OAuth)${NC}"
            show_oauth_status
            ;;
    esac
    echo ""
}

# Show OAuth provider status
show_oauth_status() {
    echo -e "        ${BLUE}OAuth Providers:${NC}"
    
    if [[ -n "${GOOGLE_CLIENT_ID:-}" ]]; then
        echo -e "        ${GREEN}• Google: Enabled${NC}"
    else
        echo -e "        ${YELLOW}• Google: Not configured${NC}"
    fi
    
    if [[ -n "${MICROSOFT_CLIENT_ID:-}" ]]; then
        echo -e "        ${GREEN}• Microsoft: Enabled${NC}"
    else
        echo -e "        ${YELLOW}• Microsoft: Not configured${NC}"
    fi
    
    if [[ -n "${GITHUB_CLIENT_ID:-}" ]]; then
        echo -e "        ${GREEN}• GitHub: Enabled${NC}"
    else
        echo -e "        ${YELLOW}• GitHub: Not configured${NC}"
    fi
}

# Show setup options
show_setup_options() {
    echo -e "${BLUE}🔧 Authentication Setup Options${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
    echo -e "${GREEN}1. Keep Local Only${NC}"
    echo -e "   • No OAuth setup needed"
    echo -e "   • Use generated admin credentials"
    echo -e "   • Perfect for development and testing"
    echo ""
    echo -e "${YELLOW}2. Add Google OAuth${NC}"
    echo -e "   • Google Workspace or Gmail accounts"
    echo -e "   • Most popular for small teams"
    echo -e "   • 5-minute setup"
    echo ""
    echo -e "${YELLOW}3. Add Microsoft OAuth${NC}"
    echo -e "   • Azure AD or Office 365 accounts"
    echo -e "   • Enterprise standard"
    echo -e "   • Supports work and personal accounts"
    echo ""
    echo -e "${YELLOW}4. Add GitHub OAuth${NC}"
    echo -e "   • GitHub accounts"
    echo -e "   • Popular with developer teams"
    echo -e "   • Organization restrictions available"
    echo ""
    echo -e "${PURPLE}5. Configure Multiple Providers${NC}"
    echo -e "   • Mix of Google, Microsoft, and GitHub"
    echo -e "   • Maximum flexibility"
    echo -e "   • Users can choose their preferred login"
    echo ""
    echo -e "${RED}6. Advanced Configuration${NC}"
    echo -e "   • Custom domain restrictions"
    echo -e "   • Role mapping rules"
    echo -e "   • Manual configuration editing"
    echo ""
}

# Setup Google OAuth
setup_google_oauth() {
    echo ""
    echo -e "${YELLOW}🔗 Google OAuth Setup${NC}"
    echo -e "${YELLOW}=====================${NC}"
    echo ""
    echo -e "${BLUE}Step 1: Create OAuth Application${NC}"
    echo "1. Go to: https://console.cloud.google.com/apis/credentials"
    echo "2. Click 'Create Credentials' → 'OAuth 2.0 Client ID'"
    echo "3. Application type: 'Web application'"
    echo "4. Name: 'Lakehouse Lab'"
    echo ""
    echo -e "${BLUE}Step 2: Configure Redirect URI${NC}"
    local host_ip="${HOST_IP:-localhost}"
    echo "Add this redirect URI:"
    echo -e "${GREEN}http://${host_ip}:9091/auth/google/callback${NC}"
    echo ""
    
    read -p "Press Enter when you've created the OAuth application..."
    echo ""
    
    read -p "Enter Google Client ID: " google_client_id
    read -s -p "Enter Google Client Secret: " google_client_secret
    echo ""
    
    # Validate inputs
    if [[ -z "$google_client_id" || -z "$google_client_secret" ]]; then
        log_error "Client ID and Secret are required"
        return 1
    fi
    
    # Update .env file
    update_env_var "GOOGLE_CLIENT_ID" "$google_client_id"
    update_env_var "GOOGLE_CLIENT_SECRET" "$google_client_secret"
    
    # Ask about domain restrictions
    echo ""
    read -p "Restrict to specific Google Workspace domain? [y/N]: " restrict_domain
    if [[ "$restrict_domain" =~ ^[Yy]$ ]]; then
        read -p "Enter domain (e.g., yourcompany.com): " google_domain
        if [[ -n "$google_domain" ]]; then
            update_env_var "COMPANY_DOMAIN" "$google_domain"
        fi
    fi
    
    log_success "Google OAuth configured successfully!"
}

# Setup Microsoft OAuth
setup_microsoft_oauth() {
    echo ""
    echo -e "${YELLOW}🔗 Microsoft OAuth Setup${NC}"
    echo -e "${YELLOW}=========================${NC}"
    echo ""
    echo -e "${BLUE}Step 1: Register Application${NC}"
    echo "1. Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps"
    echo "2. Click 'New registration'"
    echo "3. Name: 'Lakehouse Lab'"
    echo "4. Supported account types: Choose appropriate option"
    echo ""
    echo -e "${BLUE}Step 2: Configure Redirect URI${NC}"
    local host_ip="${HOST_IP:-localhost}"
    echo "Add this redirect URI (Web platform):"
    echo -e "${GREEN}http://${host_ip}:9091/auth/microsoft/callback${NC}"
    echo ""
    echo -e "${BLUE}Step 3: Create Client Secret${NC}"
    echo "1. Go to 'Certificates & secrets'"
    echo "2. Click 'New client secret'"
    echo "3. Copy the secret value (not the ID)"
    echo ""
    
    read -p "Press Enter when you've completed the setup..."
    echo ""
    
    read -p "Enter Microsoft Application (Client) ID: " ms_client_id
    read -s -p "Enter Microsoft Client Secret: " ms_client_secret
    echo ""
    
    # Ask about tenant
    echo ""
    echo -e "${BLUE}Tenant Configuration:${NC}"
    echo "• 'common' - Allows both work and personal Microsoft accounts"
    echo "• 'organizations' - Only work/school accounts"
    echo "• Specific tenant ID - Only your organization"
    echo ""
    read -p "Enter Tenant ID [common]: " ms_tenant_id
    ms_tenant_id=${ms_tenant_id:-common}
    
    # Validate inputs
    if [[ -z "$ms_client_id" || -z "$ms_client_secret" ]]; then
        log_error "Client ID and Secret are required"
        return 1
    fi
    
    # Update .env file
    update_env_var "MICROSOFT_CLIENT_ID" "$ms_client_id"
    update_env_var "MICROSOFT_CLIENT_SECRET" "$ms_client_secret"
    update_env_var "MICROSOFT_TENANT_ID" "$ms_tenant_id"
    
    log_success "Microsoft OAuth configured successfully!"
}

# Setup GitHub OAuth
setup_github_oauth() {
    echo ""
    echo -e "${YELLOW}🔗 GitHub OAuth Setup${NC}"
    echo -e "${YELLOW}=====================${NC}"
    echo ""
    echo -e "${BLUE}Step 1: Create OAuth App${NC}"
    echo "1. Go to: https://github.com/settings/applications/new"
    echo "   OR: Organization Settings → Developer settings → OAuth Apps"
    echo "2. Application name: 'Lakehouse Lab'"
    echo "3. Homepage URL: http://${HOST_IP:-localhost}:9061"
    echo ""
    echo -e "${BLUE}Step 2: Configure Authorization Callback URL${NC}"
    local host_ip="${HOST_IP:-localhost}"
    echo "Authorization callback URL:"
    echo -e "${GREEN}http://${host_ip}:9091/auth/github/callback${NC}"
    echo ""
    
    read -p "Press Enter when you've created the OAuth application..."
    echo ""
    
    read -p "Enter GitHub Client ID: " github_client_id
    read -s -p "Enter GitHub Client Secret: " github_client_secret
    echo ""
    
    # Ask about organization restrictions
    echo ""
    read -p "Restrict to specific GitHub organization? [y/N]: " restrict_org
    if [[ "$restrict_org" =~ ^[Yy]$ ]]; then
        read -p "Enter organization name: " github_org
        if [[ -n "$github_org" ]]; then
            update_env_var "GITHUB_ALLOWED_ORGS" "$github_org"
        fi
    fi
    
    # Validate inputs
    if [[ -z "$github_client_id" || -z "$github_client_secret" ]]; then
        log_error "Client ID and Secret are required"
        return 1
    fi
    
    # Update .env file
    update_env_var "GITHUB_CLIENT_ID" "$github_client_id"
    update_env_var "GITHUB_CLIENT_SECRET" "$github_client_secret"
    
    log_success "GitHub OAuth configured successfully!"
}

# Update environment variable
update_env_var() {
    local var_name="$1"
    local var_value="$2"
    
    # Remove existing line if it exists
    sed -i.bak "/^${var_name}=/d" .env
    
    # Add new line
    echo "${var_name}=${var_value}" >> .env
}

# Set authentication mode
set_auth_mode() {
    local mode="$1"
    update_env_var "AUTH_MODE" "$mode"
    
    # Ensure JWT_SECRET exists
    if ! grep -q "^JWT_SECRET=" .env; then
        local jwt_secret=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
        update_env_var "JWT_SECRET" "$jwt_secret"
    fi
}

# Generate auth configuration files
generate_auth_config() {
    log_info "Generating authentication configuration files..."
    
    # Create config directory
    mkdir -p config
    
    # Generate auth.yaml
    cat > config/auth.yaml << EOF
# Lakehouse Lab Authentication Configuration
# Generated on: $(date)

auth:
  mode: ${AUTH_MODE:-hybrid}
  jwt_secret: \${JWT_SECRET}
  
  # Local authentication (always available)
  local:
    enabled: true
    default_admin_email: \${DEFAULT_ADMIN_EMAIL:-admin@localhost}
    admin_emails: \${ADMIN_EMAILS:-admin@localhost}
    
  # OAuth providers
  oauth:
    google:
      enabled: \${GOOGLE_CLIENT_ID:+true}
      client_id: \${GOOGLE_CLIENT_ID}
      client_secret: \${GOOGLE_CLIENT_SECRET}
      allowed_domains: \${COMPANY_DOMAIN:+[\${COMPANY_DOMAIN}]}
      
    microsoft:
      enabled: \${MICROSOFT_CLIENT_ID:+true}
      client_id: \${MICROSOFT_CLIENT_ID}
      client_secret: \${MICROSOFT_CLIENT_SECRET}
      tenant_id: \${MICROSOFT_TENANT_ID:-common}
      
    github:
      enabled: \${GITHUB_CLIENT_ID:+true}
      client_id: \${GITHUB_CLIENT_ID}
      client_secret: \${GITHUB_CLIENT_SECRET}
      allowed_orgs: \${GITHUB_ALLOWED_ORGS:+[\${GITHUB_ALLOWED_ORGS}]}

  # Role mapping rules
  role_mapping:
    default_role: data_viewer
    admin_emails: \${ADMIN_EMAILS:-admin@localhost}
    company_domain: \${COMPANY_DOMAIN:-}
    
    # Role assignment rules
    rules:
      - condition: email_in_admin_list
        role: admin
      - condition: email_domain_matches_company
        role: data_analyst
      - condition: default
        role: data_viewer

# Security settings
security:
  session:
    duration_hours: 24
    refresh_enabled: true
    
  rate_limiting:
    enabled: true
    requests_per_minute: 60
    
  audit:
    enabled: true
    log_level: info
EOF

    # Generate auth-proxy.yaml
    cat > config/auth-proxy.yaml << EOF
# Lakehouse Lab Authentication Proxy Configuration
# Generated on: $(date)

proxy:
  # Service routing
  services:
    superset:
      url: \${SUPERSET_URL}
      auth_type: session_based
      admin_user: \${SUPERSET_ADMIN_USER}
      admin_password: \${SUPERSET_ADMIN_PASSWORD}
      
    airflow:
      url: \${AIRFLOW_URL}
      auth_type: basic_auth
      admin_user: \${AIRFLOW_ADMIN_USER}
      admin_password: \${AIRFLOW_ADMIN_PASSWORD}
      
    jupyter:
      url: \${JUPYTER_URL}
      auth_type: token_based
      token: \${JUPYTER_TOKEN}
      
    vizro:
      url: \${VIZRO_URL}
      auth_type: none  # Vizro doesn't have built-in auth
      
    minio:
      url: \${MINIO_CONSOLE_URL}
      auth_type: basic_auth
      admin_user: \${MINIO_ROOT_USER}
      admin_password: \${MINIO_ROOT_PASSWORD}

  # Access control
  access_control:
    data_viewer:
      allowed_services: [superset, jupyter]
      permissions:
        superset: [view_dashboards, view_charts]
        jupyter: [read_notebooks]
        
    data_analyst:
      allowed_services: [superset, jupyter, vizro]
      permissions:
        superset: [create_dashboards, edit_charts]
        jupyter: [create_notebooks, run_kernels]
        vizro: [view_dashboards, create_charts]
        
    data_engineer:
      allowed_services: [superset, jupyter, vizro, airflow, minio]
      permissions:
        airflow: [view_dags, trigger_dags]
        minio: [read_buckets, write_buckets]
        
    admin:
      allowed_services: ["*"]
      permissions: ["*"]

# Logging and monitoring
logging:
  level: \${LOG_LEVEL:-INFO}
  access_log: true
  audit_log: true
EOF

    # Generate MCP server config
    cat > config/mcp-server.yaml << EOF
# Lakehouse Lab MCP Server Configuration
# Generated on: $(date)

mcp:
  # Authentication
  auth:
    enabled: true
    auth_service_url: \${AUTH_SERVICE_URL}
    jwt_secret: \${JWT_SECRET}
    
  # Data source connections
  data_sources:
    postgres:
      url: \${POSTGRES_URL}
      pool_size: 10
      
    minio:
      endpoint: \${MINIO_ENDPOINT}
      access_key: \${MINIO_ACCESS_KEY}
      secret_key: \${MINIO_SECRET_KEY}
      
    lancedb:
      url: \${LANCEDB_URL}
      
    spark:
      master_url: \${SPARK_MASTER_URL}

  # Security settings
  security:
    rate_limiting:
      enabled: \${RATE_LIMIT_ENABLED:-true}
      requests_per_minute: 120
      
    query_limits:
      max_query_size: \${MAX_QUERY_SIZE:-100MB}
      max_execution_time: 300s
      
    audit:
      enabled: true
      log_queries: true
      log_results: false  # Don't log data, just metadata

# Tool configuration
tools:
  enabled:
    - query_postgres
    - search_vectors
    - analyze_s3_data
    - generate_insights
    - create_pipeline
    - optimize_query
EOF

    log_success "Configuration files generated in ./config/"
}

# Enable authentication services
enable_auth_services() {
    log_info "Updating service configuration to include authentication..."
    
    # Update configure-services.sh to include auth services
    if [[ -f "scripts/configure-services.sh" ]]; then
        # Check if auth services are already configured
        if ! grep -q "auth-service" scripts/configure-services.sh; then
            # Add auth services to the configuration script
            sed -i.bak '/^SERVICES\[homer\]/a\
SERVICES[auth-service]="Authentication Service (OAuth & Local)"\
SERVICES[auth-proxy]="Authentication Proxy (Service Access Control)"\
SERVICES[mcp-server]="AI-Powered Data API with Security"' scripts/configure-services.sh
            
            sed -i.bak '/^SERVICE_DESCRIPTIONS\[homer\]/a\
SERVICE_DESCRIPTIONS[auth-service]="Handles user authentication via OAuth and local accounts"\
SERVICE_DESCRIPTIONS[auth-proxy]="Proxies requests to services with role-based access control"\
SERVICE_DESCRIPTIONS[mcp-server]="AI assistant for data queries with security and audit"' scripts/configure-services.sh
            
            sed -i.bak '/^SERVICE_PORTS\[homer\]/a\
SERVICE_PORTS[auth-service]="9091"\
SERVICE_PORTS[auth-proxy]="9092"\
SERVICE_PORTS[mcp-server]="9090"' scripts/configure-services.sh
            
            sed -i.bak '/^SERVICE_RESOURCES\[homer\]/a\
SERVICE_RESOURCES[auth-service]="0.5"\
SERVICE_RESOURCES[auth-proxy]="1"\
SERVICE_RESOURCES[mcp-server]="2"' scripts/configure-services.sh
        fi
    fi
    
    log_success "Authentication services added to configuration system"
}

# Main setup function
main() {
    print_header
    
    # Check prerequisites
    check_env_file
    
    # Show current status
    show_current_status
    
    # Show options
    show_setup_options
    
    while true; do
        echo -n "Choose setup option [1-6]: "
        read -r choice
        
        case "$choice" in
            1)
                log_info "Keeping local authentication only"
                set_auth_mode "local_only"
                break
                ;;
            2)
                if setup_google_oauth; then
                    set_auth_mode "hybrid"
                    break
                fi
                ;;
            3)
                if setup_microsoft_oauth; then
                    set_auth_mode "hybrid"
                    break
                fi
                ;;
            4)
                if setup_github_oauth; then
                    set_auth_mode "hybrid"
                    break
                fi
                ;;
            5)
                setup_multiple_providers
                set_auth_mode "hybrid"
                break
                ;;
            6)
                setup_advanced_configuration
                break
                ;;
            *)
                log_error "Invalid choice. Please select 1-6."
                ;;
        esac
    done
    
    # Generate configuration files
    generate_auth_config
    
    # Enable auth services in configuration system
    enable_auth_services
    
    # Show completion message
    show_completion_message
}

# Setup multiple providers
setup_multiple_providers() {
    echo ""
    log_info "Setting up multiple OAuth providers..."
    
    echo -n "Setup Google OAuth? [y/N]: "
    read -r setup_google
    if [[ "$setup_google" =~ ^[Yy]$ ]]; then
        setup_google_oauth
    fi
    
    echo ""
    echo -n "Setup Microsoft OAuth? [y/N]: "
    read -r setup_microsoft
    if [[ "$setup_microsoft" =~ ^[Yy]$ ]]; then
        setup_microsoft_oauth
    fi
    
    echo ""
    echo -n "Setup GitHub OAuth? [y/N]: "
    read -r setup_github
    if [[ "$setup_github" =~ ^[Yy]$ ]]; then
        setup_github_oauth
    fi
}

# Advanced configuration
setup_advanced_configuration() {
    echo ""
    log_info "Advanced configuration options..."
    
    # Admin emails
    echo ""
    read -p "Enter admin email addresses (comma-separated): " admin_emails
    if [[ -n "$admin_emails" ]]; then
        update_env_var "ADMIN_EMAILS" "$admin_emails"
    fi
    
    # Company domain
    echo ""
    read -p "Enter company domain for automatic role assignment: " company_domain
    if [[ -n "$company_domain" ]]; then
        update_env_var "COMPANY_DOMAIN" "$company_domain"
    fi
    
    # Auth mode
    echo ""
    echo "Authentication modes:"
    echo "1. local_only - Only local credentials"
    echo "2. oauth - Only OAuth providers"
    echo "3. hybrid - Both local and OAuth"
    echo ""
    read -p "Choose auth mode [1-3]: " auth_mode_choice
    
    case "$auth_mode_choice" in
        1) set_auth_mode "local_only" ;;
        2) set_auth_mode "oauth" ;;
        3) set_auth_mode "hybrid" ;;
        *) set_auth_mode "hybrid" ;;
    esac
}

# Show completion message
show_completion_message() {
    echo ""
    log_success "🎉 Authentication setup complete!"
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo ""
    echo -e "${YELLOW}1. Start/Restart Services:${NC}"
    echo "   docker compose -f docker-compose.yml -f docker-compose.auth.yml down"
    echo "   docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d"
    echo ""
    echo -e "${YELLOW}2. Access Points:${NC}"
    local host_ip="${HOST_IP:-localhost}"
    echo "   • Authentication Portal: http://${host_ip}:9091"
    echo "   • Secure Service Access: http://${host_ip}:9092"
    echo "   • MCP API (if enabled):  http://${host_ip}:9090"
    echo ""
    echo -e "${YELLOW}3. View Credentials:${NC}"
    echo "   ./scripts/show-credentials.sh"
    echo ""
    echo -e "${BLUE}💡 Tips:${NC}"
    echo "• Users will now login via the authentication portal"
    echo "• Service access is automatically controlled by user roles"
    echo "• Local admin access is still available for emergencies"
    echo "• Configuration files are in ./config/ directory"
}

# Run main function
main "$@"