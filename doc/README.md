# Documentation Index

This folder contains all project documentation organized by category.

## 📖 Quick Start Guides

**Start here for common tasks:**

| Document | Purpose | When to Use |
|----------|---------|-------------|
| [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) | Query optimization patterns | When writing any code that queries the database |
| [TRANSLATION_REFACTORING_SUMMARY.md](TRANSLATION_REFACTORING_SUMMARY.md) | AI services refactoring quick reference | When working with translation or AI features |
| [DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md) | Silk & Locust setup | When doing performance testing (Day 16-17) |
| [DOCKER_SETUP.md](DOCKER_SETUP.md) | Docker commands & config | When working with Docker containers |

## 📂 Folder Structure

```
doc/
├── README.md                           # This file
│
├── OPTIMIZATION_SUMMARY.md                      # ⭐ Query optimization quick reference
├── TRANSLATION_REFACTORING_SUMMARY.md           # AI services refactoring quick ref
├── TRANSLATION_REFACTORING_PLAN.md              # AI services detailed plan
├── AI_SERVICES_ARCHITECTURE_DIAGRAM.md          # AI services architecture diagrams
├── DEVELOPMENT_TOOLS_SETUP.md                   # Silk & Locust comprehensive guide
├── DEVELOPMENT_TOOLS_README.md                  # Silk & Locust quick reference
├── DOCKER_SETUP.md                              # Docker configuration
├── RELATIONSHIPS_DIAGRAM.md                     # Database relationships
├── TEMPLATE_TAG_QUERY_MIGRATION.md              # Template tag optimization
│
├── optimization/                       # Optimization planning documents
│   ├── MASTER_OPTIMIZATION_PLAN.md     # Complete 3-week optimization plan
│   ├── READER_APP_QUERY_OPTIMIZATION_PLAN.md     # Original plan
│   └── READER_APP_QUERY_OPTIMIZATION_PLAN_V2.md  # Revised plan
│
├── reports/                            # Historical completion reports
│   ├── DAY15_REGRESSION_TESTING_REPORT.md
│   ├── WEEK1_OPTIMIZATION_RESULTS.md
│   ├── WEEK1_PILLAR1_COMPLETION_REPORT.md
│   ├── WEEK1_PILLAR2_COMPLETION_REPORT.md
│   ├── WEEK1_PILLAR3_COMPLETION_REPORT.md
│   ├── WEEK2_STAGE1_COMPLETION_REPORT.md
│   ├── WEEK2_STAGE2_COMPLETION_REPORT.md
│   ├── WEEK2_STAGE3_COMPLETION_REPORT.md
│   └── WEEK3_DAYS11-13_COMPLETION_REPORT.md
│
└── features/                           # Feature implementation docs
    ├── SEO_ANALYSIS.md
    ├── SEO_FIX_SUMMARY.md
    └── SEO_IMPLEMENTATION_SUMMARY.md
```

## 📚 Reference Documentation

### Core Guides (Use These Actively)

#### [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md)
**Quick reference for query optimization patterns**

Use this when:
- Writing any new views or querysets
- Debugging slow pages
- Adding new features that query the database

Key sections:
- Using optimized querysets (`for_list_display`, `for_detail_display`)
- View-level enrichment patterns
- Prefetch with `to_attr` pattern
- Common anti-patterns to avoid

#### [DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md)
**Comprehensive guide for Silk and Locust**

Use this when:
- Setting up performance testing tools
- Running load tests (Day 16-17 of optimization plan)
- Profiling database queries

Covers:
- Django Silk installation and usage
- Locust load testing setup
- Safety mechanisms (dev/prod separation)
- Day 16-17 testing workflow

#### [DEVELOPMENT_TOOLS_README.md](DEVELOPMENT_TOOLS_README.md)
**Quick reference for development tools**

Condensed version of setup guide with:
- Quick start commands
- Common troubleshooting
- Environment configuration

#### [DOCKER_SETUP.md](DOCKER_SETUP.md)
**Docker configuration and commands**

Use this when:
- Setting up development environment with Docker
- Troubleshooting container issues
- Understanding service configuration

#### [RELATIONSHIPS_DIAGRAM.md](RELATIONSHIPS_DIAGRAM.md)
**Database relationships overview**

Visual overview of:
- Model relationships
- Foreign key connections
- Database schema

#### [TEMPLATE_TAG_QUERY_MIGRATION.md](TEMPLATE_TAG_QUERY_MIGRATION.md)
**Template tag optimization guide**

Use this when:
- Creating new template tags
- Migrating old template tags to use context
- Understanding zero-query template patterns

#### [TRANSLATION_REFACTORING_SUMMARY.md](TRANSLATION_REFACTORING_SUMMARY.md)
**AI services refactoring quick reference**

Use this when:
- Working with translation or analysis features
- Understanding the modular AI architecture
- Switching between OpenAI and Gemini providers
- Understanding provider abstraction

Quick sections:
- Current problems with OpenAI-only design
- New modular architecture overview
- Usage examples and configuration
- Migration timeline

#### [TRANSLATION_REFACTORING_PLAN.md](TRANSLATION_REFACTORING_PLAN.md)
**Detailed AI services refactoring plan**

Use this when:
- Implementing the modular AI architecture
- Understanding the 6-week implementation phases
- Adding new AI providers
- Deep dive into architecture decisions

Covers:
- Current architecture analysis
- Proposed architecture with code examples
- Phase-by-phase implementation plan
- Testing strategy and success criteria

#### [AI_SERVICES_ARCHITECTURE_DIAGRAM.md](AI_SERVICES_ARCHITECTURE_DIAGRAM.md)
**Visual AI services architecture diagrams**

Use this when:
- Understanding data flow through the AI system
- Visualizing provider abstraction
- Understanding request/response flow
- Seeing configuration hierarchy

Includes:
- High-level architecture diagram
- Request flow diagrams
- Provider implementation flows
- Package structure visualization

## 📁 Historical Documentation

### Optimization Plans ([optimization/](optimization/))

Original planning documents for the 3-week optimization project:

- **[MASTER_OPTIMIZATION_PLAN.md](optimization/MASTER_OPTIMIZATION_PLAN.md)** - Complete 3-week roadmap with goals and success criteria
- **[READER_APP_QUERY_OPTIMIZATION_PLAN.md](optimization/READER_APP_QUERY_OPTIMIZATION_PLAN.md)** - Original optimization plan
- **[READER_APP_QUERY_OPTIMIZATION_PLAN_V2.md](optimization/READER_APP_QUERY_OPTIMIZATION_PLAN_V2.md)** - Revised plan with updated strategy

**Note:** These are historical planning documents. For current best practices, use [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md).

### Completion Reports ([reports/](reports/))

Weekly completion reports documenting progress:

| Report | Period | Focus |
|--------|--------|-------|
| [WEEK1_PILLAR1_COMPLETION_REPORT.md](reports/WEEK1_PILLAR1_COMPLETION_REPORT.md) | Week 1 | BookQuerySet optimization |
| [WEEK1_PILLAR2_COMPLETION_REPORT.md](reports/WEEK1_PILLAR2_COMPLETION_REPORT.md) | Week 1 | View enrichment patterns |
| [WEEK1_PILLAR3_COMPLETION_REPORT.md](reports/WEEK1_PILLAR3_COMPLETION_REPORT.md) | Week 1 | Template tag migration |
| [WEEK1_OPTIMIZATION_RESULTS.md](reports/WEEK1_OPTIMIZATION_RESULTS.md) | Week 1 | Summary & metrics |
| [WEEK2_STAGE1_COMPLETION_REPORT.md](reports/WEEK2_STAGE1_COMPLETION_REPORT.md) | Week 2 | Additional optimizations |
| [WEEK2_STAGE2_COMPLETION_REPORT.md](reports/WEEK2_STAGE2_COMPLETION_REPORT.md) | Week 2 | Advanced patterns |
| [WEEK2_STAGE3_COMPLETION_REPORT.md](reports/WEEK2_STAGE3_COMPLETION_REPORT.md) | Week 2 | Final refinements |
| [WEEK3_DAYS11-13_COMPLETION_REPORT.md](reports/WEEK3_DAYS11-13_COMPLETION_REPORT.md) | Week 3 | Analytics & stats |
| [DAY15_REGRESSION_TESTING_REPORT.md](reports/DAY15_REGRESSION_TESTING_REPORT.md) | Week 3 | Regression testing |

### Feature Documentation ([features/](features/))

SEO implementation documentation:

- **[SEO_ANALYSIS.md](features/SEO_ANALYSIS.md)** - Initial SEO audit and issues
- **[SEO_FIX_SUMMARY.md](features/SEO_FIX_SUMMARY.md)** - Quick summary of fixes
- **[SEO_IMPLEMENTATION_SUMMARY.md](features/SEO_IMPLEMENTATION_SUMMARY.md)** - Complete implementation details

## 🎯 Common Tasks

### I need to write a new view that displays books
1. Read [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) sections:
   - "Using Optimized QuerySets"
   - "View-Level Enrichment Patterns"
2. Use `.for_list_display()` or `.for_detail_display()`
3. Call enrichment methods in `get_context_data()`

### I need to create a new template tag
1. Read [TEMPLATE_TAG_QUERY_MIGRATION.md](TEMPLATE_TAG_QUERY_MIGRATION.md)
2. Make it context-aware (use prefetched data)
3. Verify zero queries with Debug Toolbar

### I need to set up performance testing
1. Read [DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md)
2. Install: `pip install -r requirements/development.txt`
3. Set `ENVIRONMENT=development` in `.env`
4. Run migrations: `python manage.py migrate`
5. Access Silk at `/silk/`

### I need to understand the database schema
1. Read [RELATIONSHIPS_DIAGRAM.md](RELATIONSHIPS_DIAGRAM.md)
2. Look at model files in `myapp/books/models/`

### I need to run the app with Docker
1. Read [DOCKER_SETUP.md](DOCKER_SETUP.md)
2. Run: `docker-compose up`

### I need to work on translation or AI features
1. Read [TRANSLATION_REFACTORING_SUMMARY.md](TRANSLATION_REFACTORING_SUMMARY.md) for overview
2. Check [AI_SERVICES_ARCHITECTURE_DIAGRAM.md](AI_SERVICES_ARCHITECTURE_DIAGRAM.md) for visuals
3. See [TRANSLATION_REFACTORING_PLAN.md](TRANSLATION_REFACTORING_PLAN.md) for detailed implementation

### I need to switch from OpenAI to Gemini (or vice versa)
1. Read configuration section in [TRANSLATION_REFACTORING_SUMMARY.md](TRANSLATION_REFACTORING_SUMMARY.md)
2. Update settings or environment variables
3. No code changes needed!

## 📖 Reading Order for New Developers

If you're new to the codebase:

1. **[RELATIONSHIPS_DIAGRAM.md](RELATIONSHIPS_DIAGRAM.md)** - Understand the data model
2. **[OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md)** - Learn the coding patterns
3. **[DOCKER_SETUP.md](DOCKER_SETUP.md)** - Set up your environment
4. **[DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md)** - Learn the testing tools

## 🔗 External Links

- Django Documentation: https://docs.djangoproject.com/
- Django Debug Toolbar: https://django-debug-toolbar.readthedocs.io/
- Django Silk: https://github.com/jazzband/django-silk
- Locust: https://docs.locust.io/

## 📝 Document Update Log

| Date | Document | Change |
|------|----------|--------|
| 2025-12-06 | Added AI services refactoring docs | TRANSLATION_REFACTORING_PLAN.md, TRANSLATION_REFACTORING_SUMMARY.md, AI_SERVICES_ARCHITECTURE_DIAGRAM.md |
| 2025-11-29 | Initial structure | Core optimization and development docs |

---

**Last Updated:** 2025-12-06
**Maintained By:** Project Team
