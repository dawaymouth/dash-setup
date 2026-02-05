# Dashboard Customization Guide

This guide explains how to customize this dashboard template to create your own metrics dashboard.

## Quick Start: Creating Your Dashboard

### Step 1: Create from Template

On GitHub:
1. Navigate to [github.com/dawaymouth/dash-setup](https://github.com/dawaymouth/dash-setup)
2. Click **"Use this template"** → **"Create a new repository"**
3. Name your repository (e.g., `supplier-dashboard`, `orders-dashboard`)
4. Clone your new repository locally

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME
./setup.sh
```

### Step 2: Plan Your Dashboard

Before coding, answer these questions:

1. **What metrics do you want to show?**
   - List 3-5 main metrics
   - What questions should the dashboard answer?

2. **What data do you need?**
   - Which Redshift tables/schemas?
   - What filters make sense (date range, categories, etc.)?

3. **What visualizations work best?**
   - Line charts for trends over time
   - Bar charts for comparisons
   - Summary cards for key numbers

### Step 3: Customize (See sections below)

1. Modify backend queries
2. Update frontend components
3. Test and iterate

---

## Project Structure Overview

```
your-dashboard/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app, routes registered here
│   │   ├── database.py       # Redshift connection (usually unchanged)
│   │   ├── models.py         # Pydantic models for API responses
│   │   └── routers/          # API endpoints (one file per metric group)
│   │       ├── volume.py     # Example: volume metrics
│   │       ├── cycle_time.py # Example: cycle time metrics
│   │       └── ...
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/       # React components (one per metric group)
│   │   │   ├── Dashboard.tsx # Main dashboard layout
│   │   │   ├── FilterBar.tsx # Date/filter controls
│   │   │   └── VolumeMetrics.tsx # Example: volume charts
│   │   ├── hooks/
│   │   │   └── useMetrics.ts # React Query hooks for API calls
│   │   ├── api.ts            # Axios API client
│   │   └── types.ts          # TypeScript type definitions
│   └── package.json
└── README.md
```

---

## Customizing Backend (API & Queries)

### Adding a New Metric Endpoint

**Step 1: Create a new router file**

Create `backend/app/routers/your_metric.py`:

```python
"""
Your metric API endpoints.
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query
from typing import Optional

from app.database import execute_query
from app.models import YourMetricResponse  # Define this in models.py

router = APIRouter()


@router.get("/summary", response_model=YourMetricResponse)
async def get_your_metric(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
):
    """Get your metric summary."""
    
    # Default date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    # Your SQL query
    query = f"""
        SELECT 
            COUNT(*) as total_count,
            SUM(amount) as total_amount
        FROM your_schema.your_table
        WHERE created_at >= '{start_date}'
          AND created_at < '{end_date + timedelta(days=1)}'
    """
    
    results = execute_query(query)
    
    return {
        "total_count": results[0]["total_count"] if results else 0,
        "total_amount": results[0]["total_amount"] if results else 0,
    }
```

**Step 2: Define response models**

Add to `backend/app/models.py`:

```python
from pydantic import BaseModel

class YourMetricResponse(BaseModel):
    total_count: int
    total_amount: float
```

**Step 3: Register the router**

Add to `backend/app/main.py`:

```python
from app.routers import your_metric

# Add with other router includes
app.include_router(
    your_metric.router, 
    prefix="/api/your-metric", 
    tags=["Your Metric"]
)
```

**Step 4: Test the endpoint**

```bash
# Start the backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Test in browser or curl
curl http://localhost:8000/api/your-metric/summary
```

### Common SQL Query Patterns

**Date filtering:**
```python
def get_date_filter(start_date: date, end_date: date, column: str = "created_at") -> str:
    return f"{column} >= '{start_date}' AND {column} < '{end_date + timedelta(days=1)}'"
```

**Aggregation by time period:**
```python
# Daily
query = """
    SELECT DATE(created_at) as date, COUNT(*) as count
    FROM your_table
    GROUP BY DATE(created_at)
    ORDER BY date
"""

# Weekly
query = """
    SELECT DATE_TRUNC('week', created_at) as week, COUNT(*) as count
    FROM your_table
    GROUP BY DATE_TRUNC('week', created_at)
    ORDER BY week
"""

# Monthly
query = """
    SELECT DATE_TRUNC('month', created_at) as month, COUNT(*) as count
    FROM your_table
    GROUP BY DATE_TRUNC('month', created_at)
    ORDER BY month
"""
```

**Joining tables:**
```python
query = """
    SELECT 
        t.id,
        t.name,
        s.supplier_name
    FROM your_schema.main_table t
    LEFT JOIN your_schema.suppliers s ON t.supplier_id = s.id
    WHERE t.created_at >= '{start_date}'
"""
```

**With filters:**
```python
query = f"""
    SELECT COUNT(*) as count
    FROM your_table
    WHERE created_at >= '{start_date}'
      AND created_at < '{end_date}'
      {'AND supplier_id = ' + repr(supplier_id) if supplier_id else ''}
      {'AND category = ' + repr(category) if category else ''}
"""
```

---

## Customizing Frontend (UI & Charts)

### Adding a New Metrics Component

**Step 1: Create the component**

Create `frontend/src/components/YourMetrics.tsx`:

```tsx
import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import type { FilterState } from '../types';
import { useYourMetric } from '../hooks/useMetrics';

interface YourMetricsProps {
  filters: FilterState;
}

export const YourMetrics: React.FC<YourMetricsProps> = ({ filters }) => {
  const { data, isLoading, error } = useYourMetric(filters);

  if (isLoading) {
    return <div className="animate-pulse bg-gray-200 h-64 rounded-lg" />;
  }

  if (error) {
    return <div className="text-red-500">Error loading data</div>;
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold mb-4 text-yourColor-600">
        Your Metrics
      </h2>
      
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-yourColor-50 p-4 rounded-lg">
          <p className="text-sm text-yourColor-600">Total Count</p>
          <p className="text-2xl font-bold text-yourColor-700">
            {data?.total_count?.toLocaleString() ?? 0}
          </p>
        </div>
        {/* Add more summary cards */}
      </div>
      
      {/* Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data?.trend || []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line 
              type="monotone" 
              dataKey="count" 
              stroke="#yourColor" 
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
```

**Step 2: Add the API hook**

Add to `frontend/src/hooks/useMetrics.ts`:

```tsx
export function useYourMetric(filters: FilterState) {
  return useQuery({
    queryKey: ['yourMetric', filters],
    queryFn: async () => {
      const params = new URLSearchParams({
        start_date: filters.startDate,
        end_date: filters.endDate,
      });
      
      if (filters.supplierId) {
        params.append('supplier_id', filters.supplierId);
      }
      
      const response = await api.get(`/api/your-metric/summary?${params}`);
      return response.data;
    },
  });
}
```

**Step 3: Add to Dashboard**

Update `frontend/src/components/Dashboard.tsx`:

```tsx
import { YourMetrics } from './YourMetrics';

// In the JSX:
<div className="space-y-6">
  {/* Existing metrics */}
  <VolumeMetrics filters={filters} />
  
  {/* Your new metrics */}
  <YourMetrics filters={filters} />
</div>
```

**Step 4: Export the component**

Update `frontend/src/components/index.ts`:

```tsx
export { YourMetrics } from './YourMetrics';
```

### Chart Types Reference

**Line Chart (trends over time):**
```tsx
<LineChart data={data}>
  <XAxis dataKey="date" />
  <YAxis />
  <Line type="monotone" dataKey="value" stroke="#8884d8" />
</LineChart>
```

**Bar Chart (comparisons):**
```tsx
<BarChart data={data}>
  <XAxis dataKey="category" />
  <YAxis />
  <Bar dataKey="count" fill="#82ca9d" />
</BarChart>
```

**Pie Chart (distribution):**
```tsx
import { PieChart, Pie, Cell } from 'recharts';

<PieChart>
  <Pie data={data} dataKey="value" nameKey="name">
    {data.map((entry, index) => (
      <Cell key={index} fill={COLORS[index % COLORS.length]} />
    ))}
  </Pie>
</PieChart>
```

**Area Chart (volume/cumulative):**
```tsx
<AreaChart data={data}>
  <XAxis dataKey="date" />
  <YAxis />
  <Area type="monotone" dataKey="value" fill="#8884d8" stroke="#8884d8" />
</AreaChart>
```

### Adding Custom Colors

Update `frontend/tailwind.config.js`:

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        yourMetric: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
      },
    },
  },
};
```

---

## Adding Filters

### Backend: Accept Filter Parameters

```python
@router.get("/summary")
async def get_summary(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    # Build dynamic WHERE clause
    conditions = [f"created_at >= '{start_date}'"]
    
    if category:
        conditions.append(f"category = '{category}'")
    if status:
        conditions.append(f"status = '{status}'")
    
    where_clause = " AND ".join(conditions)
    
    query = f"SELECT COUNT(*) FROM your_table WHERE {where_clause}"
    return execute_query(query)
```

### Frontend: Add Filter Controls

Update `frontend/src/components/FilterBar.tsx`:

```tsx
// Add new filter state
const [category, setCategory] = useState<string | null>(null);

// Add to filter bar JSX
<select
  value={category || ''}
  onChange={(e) => setCategory(e.target.value || null)}
  className="rounded-md border-gray-300"
>
  <option value="">All Categories</option>
  <option value="type_a">Type A</option>
  <option value="type_b">Type B</option>
</select>
```

Update `frontend/src/types.ts`:

```typescript
export interface FilterState {
  startDate: string;
  endDate: string;
  supplierId: string | null;
  category: string | null;  // Add new filter
}
```

---

## Common Customizations

### Rename the Dashboard

1. Update `frontend/src/App.tsx` - Change the title
2. Update `README.md` - Update description
3. Update `backend/app/main.py` - Update API title

### Change the Color Scheme

This dashboard uses Tailwind CSS color classes:
- `volume` = green
- `cycleTime` = red
- `productivity` = fuchsia/purple
- `accuracy` = blue

To change, update:
1. `frontend/tailwind.config.js` - Define new colors
2. Component files - Use new color classes

### Remove Unused Metrics

1. Delete the router file in `backend/app/routers/`
2. Remove the router include in `backend/app/main.py`
3. Delete the component in `frontend/src/components/`
4. Remove the import/usage in `Dashboard.tsx`
5. Remove the hook in `useMetrics.ts`

### Add Authentication (Advanced)

For simple auth, consider:
- FastAPI OAuth2 with JWT
- Basic HTTP auth
- Environment variable API key

```python
# Simple API key auth
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Use as dependency
@router.get("/protected", dependencies=[Depends(verify_api_key)])
async def protected_endpoint():
    return {"message": "Authenticated!"}
```

---

## Testing Your Changes

### Backend Testing

```bash
cd backend
source venv/bin/activate

# Run the server
uvicorn app.main:app --reload --port 8000

# Test endpoints
curl http://localhost:8000/api/your-endpoint/summary

# View API docs
open http://localhost:8000/docs
```

### Frontend Testing

```bash
cd frontend

# Run development server
npm run dev

# Build for production (check for errors)
npm run build

# Type checking
npm run lint
```

### Full Stack Testing

```bash
# From project root
./start.sh

# Dashboard opens in browser
# Test all features manually
# Check browser console for errors
```

---

## Deploying Your Dashboard

### Share with Team (Local)

Your dashboard inherits the same scripts:
- `./setup.sh` - One-command setup
- `./start.sh` - Start dashboard
- `./update.sh` - Get updates

Team members clone your repo and run `./setup.sh`.

### Add to Dashboard Hub

If your team uses Dashboard Hub:

1. Push your dashboard to GitHub
2. Fork the `dashboard-hub` repository
3. Add entry to `gallery.json`:
```json
{
  "id": "your-dashboard",
  "name": "Your Dashboard Name",
  "owner": "Your Name",
  "repo": "https://github.com/you/your-dashboard.git",
  "description": "What your dashboard shows",
  "port": 5174
}
```
4. Submit PR to dashboard-hub

---

## Troubleshooting

### "Module not found" errors

```bash
# Backend
cd backend && pip install -r requirements.txt

# Frontend
cd frontend && npm install
```

### SQL query errors

1. Test query in Redshift directly first
2. Check date formatting matches Redshift expectations
3. Verify table/schema names are correct
4. Check column names match exactly

### Frontend not updating

```bash
# Clear cache and restart
cd frontend
rm -rf node_modules/.vite
npm run dev
```

### TypeScript errors

```bash
# Check types
cd frontend && npm run lint

# Common fixes:
# - Add missing type definitions to types.ts
# - Check API response matches expected type
```

---

## Examples

### Example: Simple Counter Dashboard

**Backend** (`backend/app/routers/counter.py`):
```python
@router.get("/total")
async def get_total():
    result = execute_query("SELECT COUNT(*) as total FROM my_table")
    return {"total": result[0]["total"]}
```

**Frontend** (`frontend/src/components/Counter.tsx`):
```tsx
export const Counter = () => {
  const { data } = useQuery({
    queryKey: ['total'],
    queryFn: () => api.get('/api/counter/total').then(r => r.data)
  });
  
  return (
    <div className="text-4xl font-bold">
      {data?.total?.toLocaleString()}
    </div>
  );
};
```

### Example: Time Series Dashboard

**Backend**:
```python
@router.get("/trend")
async def get_trend(days: int = 30):
    query = f"""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM my_table
        WHERE created_at >= CURRENT_DATE - INTERVAL '{days} days'
        GROUP BY DATE(created_at)
        ORDER BY date
    """
    return execute_query(query)
```

**Frontend**:
```tsx
<LineChart data={trendData}>
  <XAxis dataKey="date" />
  <YAxis />
  <Line dataKey="count" stroke="#8884d8" />
</LineChart>
```

---

## Need Help?

- Check existing routers/components for patterns
- Review [Recharts documentation](https://recharts.org/)
- Review [FastAPI documentation](https://fastapi.tiangolo.com/)
- Review [Tailwind CSS documentation](https://tailwindcss.com/)
- Ask in team Slack channel

---

**Happy dashboard building!**
