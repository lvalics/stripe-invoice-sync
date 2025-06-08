# TODO - Stripe Invoice Sync

## Critical Missing Features (from IMPLEMENTATION.md)

### 1. Database Persistence Layer (High Priority)
- [ ] Implement SQLAlchemy models for:
  - [ ] Processed invoices tracking
  - [ ] Processing history and status
  - [ ] Audit trails
  - [ ] Failed invoice retry queue
- [ ] Add database migrations with Alembic
- [ ] Create database service layer for CRUD operations
- [ ] Implement duplicate detection before processing
- [ ] Add transaction support for atomic operations

### 2. State Management (High Priority)
- [ ] Track processed Stripe invoice IDs to prevent duplicates
- [ ] Store processing results and timestamps
- [ ] Implement retry mechanism for failed invoices
- [ ] Add status tracking (pending, processing, completed, failed)
- [ ] Create cleanup jobs for old records

### 3. Authentication & Security (Medium Priority)
- [ ] Implement OAuth2 flow for ANAF (currently using basic auth)
- [ ] Add API authentication (JWT or API keys)
- [ ] Implement rate limiting per API key
- [ ] Add request validation and sanitization
- [ ] Secure credential storage in database

### 4. Webhook Support (Medium Priority)
- [ ] Implement Stripe webhook endpoint
- [ ] Add webhook signature verification
- [ ] Create auto-processing on invoice.created events
- [ ] Add webhook retry logic
- [ ] Implement webhook event deduplication

### 5. Notification System (Medium Priority)
- [ ] Email notifications for:
  - [ ] Processing completion
  - [ ] Processing failures
  - [ ] Daily summary reports
- [ ] Add notification preferences per tenant
- [ ] Implement notification templates
- [ ] Add webhook notifications option

### 6. Testing Infrastructure (Medium Priority)
- [ ] Unit tests for:
  - [ ] XML generation
  - [ ] Provider implementations
  - [ ] Data transformations
- [ ] Integration tests for API endpoints
- [ ] End-to-end tests with mock providers
- [ ] Performance tests for batch processing
- [ ] Add CI/CD pipeline configuration

### 7. Monitoring & Logging (Low Priority)
- [ ] Implement structured logging with correlation IDs
- [ ] Add Sentry error tracking
- [ ] Create performance metrics
- [ ] Add health check endpoints with detailed status
- [ ] Implement audit logging for all operations

### 8. Advanced Features (Low Priority)
- [ ] Credit note handling
- [ ] Multi-currency automatic conversion
- [ ] Invoice templates system
- [ ] Bulk operations (download, status check)
- [ ] Invoice scheduling
- [ ] Custom field mapping per tenant

## Multitenant Architecture Implementation

### Phase 1: Database Foundation
- [ ] Design tenant data model:
  ```sql
  tenants (id, name, slug, active, created_at)
  tenant_credentials (tenant_id, provider, credentials_encrypted, company_info)
  tenant_settings (tenant_id, key, value)
  tenant_invoices (tenant_id, stripe_id, provider_id, status, processed_at)
  ```
- [ ] Implement credential encryption/decryption service
- [ ] Create tenant management service
- [ ] Add database connection pooling per tenant

### Phase 2: Authentication Infrastructure
- [ ] Implement JWT authentication middleware
- [ ] Create tenant resolver from JWT claims
- [ ] Add API key authentication option
- [ ] Implement tenant context injection
- [ ] Add role-based access control (admin, user)

### Phase 3: Provider Isolation
- [ ] Refactor ProviderFactory to support per-request instantiation
- [ ] Create TenantProviderFactory:
  ```python
  async def create_provider(tenant_id: str, provider_name: str):
      credentials = await get_tenant_credentials(tenant_id, provider_name)
      return provider_class(**credentials)
  ```
- [ ] Implement provider credential caching with TTL
- [ ] Add provider health check per tenant

### Phase 4: API Modifications
- [ ] Add tenant context to all endpoints:
  ```python
  @router.post("/process")
  async def process_invoice(
      invoice: InvoiceRequest,
      tenant: Tenant = Depends(get_current_tenant)
  ):
      provider = await get_tenant_provider(tenant.id, invoice.provider)
  ```
- [ ] Create tenant management endpoints:
  - [ ] POST /api/tenants - Create tenant
  - [ ] GET /api/tenants/{id} - Get tenant info
  - [ ] PUT /api/tenants/{id}/credentials - Update credentials
  - [ ] DELETE /api/tenants/{id} - Deactivate tenant
- [ ] Add tenant filtering to all list operations

### Phase 5: Stripe Service Multitenancy
- [ ] Modify StripeService to accept tenant-specific API keys
- [ ] Implement Stripe webhook routing by tenant
- [ ] Add tenant identification from Stripe metadata
- [ ] Create per-tenant Stripe sync settings

### Phase 6: Data Isolation
- [ ] Implement row-level security in database
- [ ] Add tenant_id to all data models
- [ ] Create tenant-scoped queries
- [ ] Implement data retention policies per tenant
- [ ] Add tenant data export functionality

### Phase 7: Deployment & Operations
- [ ] Create Docker Compose for multi-tenant setup
- [ ] Add environment-based configuration overrides
- [ ] Implement zero-downtime deployment strategy
- [ ] Create tenant onboarding automation
- [ ] Add monitoring per tenant

### Phase 8: Admin Interface
- [ ] Create admin API endpoints for:
  - [ ] Tenant management
  - [ ] Credential management
  - [ ] System monitoring
  - [ ] Billing/usage tracking
- [ ] Add super-admin authentication
- [ ] Implement audit trails for admin actions

## Migration Path

### Option 1: Full Multitenant (Recommended for SaaS)
1. Implement database layer with tenant support
2. Add authentication middleware
3. Refactor providers for per-request instantiation
4. Migrate existing single-tenant deployments
5. Add tenant management UI

### Option 2: Multi-Instance (Simpler Alternative)
1. Containerize application with Docker
2. Create orchestration layer (Kubernetes/Docker Swarm)
3. Deploy separate instance per client
4. Use reverse proxy for routing
5. Implement centralized monitoring

## Performance Considerations

- [ ] Implement connection pooling per tenant
- [ ] Add Redis caching for:
  - [ ] Tenant credentials (encrypted)
  - [ ] Provider instances
  - [ ] Processing status
- [ ] Optimize database queries with indexes
- [ ] Implement async processing queues
- [ ] Add request timeout handling

## Security Requirements

- [ ] Encrypt all tenant credentials at rest
- [ ] Implement key rotation mechanism
- [ ] Add audit logging for credential access
- [ ] Implement IP whitelisting per tenant
- [ ] Add rate limiting per tenant
- [ ] Create security headers middleware
- [ ] Implement CORS configuration per tenant

## Monitoring & Analytics

- [ ] Track per-tenant metrics:
  - [ ] API usage
  - [ ] Processing success/failure rates
  - [ ] Response times
  - [ ] Error rates
- [ ] Create tenant dashboards
- [ ] Implement usage-based billing hooks
- [ ] Add alerting for tenant-specific issues

## Documentation Updates

- [ ] Create multitenant deployment guide
- [ ] Document tenant onboarding process
- [ ] Add API authentication examples
- [ ] Create troubleshooting guide
- [ ] Document backup/restore procedures

## Estimated Timeline

- **Phase 1-2**: 2-3 weeks (Database & Authentication)
- **Phase 3-4**: 2-3 weeks (Provider Isolation & API)
- **Phase 5-6**: 1-2 weeks (Stripe & Data Isolation)
- **Phase 7-8**: 2-3 weeks (Deployment & Admin)
- **Total**: 7-11 weeks for full multitenant implementation

## Priority Order

1. **Must Have**: Database persistence (prevent duplicates)
2. **Should Have**: Basic multitenancy (API keys, tenant isolation)
3. **Nice to Have**: Full admin interface, monitoring dashboard
4. **Future**: React frontend, advanced analytics