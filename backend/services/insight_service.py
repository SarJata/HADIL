import pandas as pd
import numpy as np
import re
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def is_id_column(col_name: str) -> bool:
    """
    Returns True if the column is an ID, primary key, or foreign key column.
    ID columns must not be used for generic average or min/max statistical takeaways.
    """
    c_lower = str(col_name).lower().strip()
    if c_lower == 'id':
        return True
    if c_lower.endswith('_id') or c_lower.endswith('id'):
        if any(x in c_lower for x in ['user', 'customer', 'album', 'artist', 'order', 'invoice', 'track', 'genre', 'playlist', 'employee', 'media', 'product', 'item']):
            return True
    return False

def generate_insights(data: List[Dict[str, Any]], query: Optional[str] = None, sql: Optional[str] = None) -> List[str]:
    """
    Generates query-relevant insights ONLY when they directly answer, explain, or contextualize
    the user's original natural-language question.
    
    Returns [] (empty list) when there are no meaningful, query-specific takeaways.
    Does NOT invoke any LLM API call.
    """
    if not data or len(data) == 0:
        return []

    try:
        df = pd.DataFrame(data)
        if df.empty:
            return []

        q_lower = query.lower().strip() if query else ""
        sql_lower = sql.lower().strip() if sql else ""
        columns = list(df.columns)

        # Filter out ID / primary key columns for statistical analysis
        valid_cols = [c for c in columns if not is_id_column(c)]
        num_cols = [c for c in valid_cols if pd.api.types.is_numeric_dtype(df[c])]
        cat_cols = [c for c in valid_cols if not pd.api.types.is_numeric_dtype(df[c])]

        # Check for plain data dump / generic retrieval queries (e.g., "Show me all users", "Show me customers")
        is_generic_dump = False
        if not q_lower or any(p in q_lower for p in [
            "show me all", "show all", "list all", "get all", "select all",
            "show me users", "show users", "show me customers", "show customers",
            "show me orders", "show orders", "show me products", "show products",
            "show data from", "display all"
        ]) and not any(w in q_lower for w in ["top", "highest", "most", "average", "avg", "total", "sum", "count", "each", "group", "by"]):
            is_generic_dump = True

        if is_generic_dump and "group by" not in sql_lower and "count(" not in sql_lower and "sum(" not in sql_lower and "avg(" not in sql_lower:
            return []

        insights = []

        # Scenario 1: Ranking / Top N Queries (e.g., "What are the top 5 albums by revenue?", "top selling products")
        if any(w in q_lower for w in ["top", "highest", "best", "most revenue", "leading", "greatest"]) or ("order by" in sql_lower and "desc" in sql_lower):
            metric_col = next((c for c in num_cols if any(m in c.lower() for m in ["total", "revenue", "amount", "sales", "count", "price", "sum", "val"])), None)
            if not metric_col and num_cols:
                metric_col = num_cols[0]

            entity_col = next((c for c in cat_cols if any(e in c.lower() for e in ["name", "title", "customer", "album", "artist", "product", "country"])), None)
            if not entity_col and cat_cols:
                entity_col = cat_cols[0]

            if entity_col and metric_col and len(df) > 0:
                top_row = df.sort_values(by=metric_col, ascending=False).iloc[0]
                entity_val = top_row[entity_col]
                metric_val = top_row[metric_col]
                
                is_currency = any(curr in metric_col.lower() or curr in q_lower for curr in ["revenue", "price", "amount", "total", "sales", "val", "cost", "dollar", "$"])
                formatted_val = f"${metric_val:,.2f}" if is_currency else f"{metric_val:,.0f}" if isinstance(metric_val, (int, np.integer)) else f"{metric_val:,.2f}"
                
                insights.append(f"'{entity_val}' generated the highest {metric_col} ({formatted_val}) among the top results.")
                return insights

        # Scenario 2: Aggregation / Category Count Queries (e.g., "How many customers are from each country?", "Which country has the most customers?")
        if any(w in q_lower for w in ["each", "per", "by country", "by status", "by category", "how many", "count", "distribution"]) or "group by" in sql_lower:
            category_col = next((c for c in cat_cols if any(cat in c.lower() for cat in ["country", "status", "category", "type", "genre", "state", "city"])), None)
            if not category_col and cat_cols:
                category_col = cat_cols[0]

            count_col = next((c for c in num_cols if any(cnt in c.lower() for cnt in ["count", "total", "num", "customers", "orders", "users", "quantity"])), None)

            if category_col:
                if count_col:
                    top_row = df.sort_values(by=count_col, ascending=False).iloc[0]
                    top_cat = top_row[category_col]
                    top_val = top_row[count_col]
                    count_str = f"{int(top_val):,}" if isinstance(top_val, (int, np.integer, float)) else str(top_val)
                    insights.append(f"'{top_cat}' has the highest number of records ({count_str}).")
                    return insights
                else:
                    counts = df[category_col].value_counts()
                    if not counts.empty:
                        top_cat = counts.idxmax()
                        top_count = counts.max()
                        insights.append(f"'{top_cat}' has the highest number of customers ({top_count}).")
                        return insights

        # Scenario 3: Average / Total / Specific Metric Queries (e.g., "What is the average order value?", "What is total revenue?")
        if any(w in q_lower for w in ["average", "avg", "mean", "total", "sum"]) and num_cols:
            target_metric = next((c for c in num_cols if any(m in c.lower() for m in ["amount", "total", "price", "val", "cost", "revenue", "sales"])), num_cols[0])
            
            if "average" in q_lower or "avg" in q_lower or "mean" in q_lower:
                avg_val = df[target_metric].mean()
                is_currency = any(curr in target_metric.lower() or curr in q_lower for curr in ["amount", "price", "revenue", "sales", "val", "cost", "$", "dollar", "order"])
                formatted_avg = f"${avg_val:,.2f}" if is_currency else f"{avg_val:,.2f}"
                insights.append(f"The average {target_metric} is {formatted_avg}.")
                return insights

            if "total" in q_lower or "sum" in q_lower:
                tot_val = df[target_metric].sum()
                is_currency = any(curr in target_metric.lower() or curr in q_lower for curr in ["amount", "price", "revenue", "sales", "val", "cost", "$", "dollar"])
                formatted_tot = f"${tot_val:,.2f}" if is_currency else f"{tot_val:,.2f}"
                insights.append(f"The total {target_metric} is {formatted_tot}.")
                return insights

        # Default fallback: return [] when no query-specific takeaway applies
        return []

    except Exception as e:
        logger.error(f"Error generating query-relevant insights: {e}")
        return []

def predict_trend(data: List[Dict[str, Any]], query: Optional[str] = None, sql: Optional[str] = None) -> Dict[str, Any]:
    if not data or len(data) < 3:
        return {"error": "Insufficient data for prediction (need at least 3 records)."}
    
    try:
        df = pd.DataFrame(data)
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        from ai_modules.context_analyzer import extract_query_context
        context = extract_query_context(query, sql) if query and sql else None
        
        time_col = None
        for col in cat_cols:
            if any(word in col.lower() for word in ['date', 'time', 'created', 'year', 'month']):
                try:
                    df[col] = pd.to_datetime(df[col])
                    time_col = col
                    break
                except: pass
        
        if not num_cols:
            return {"error": "No numeric data found to perform forecasting."}
        
        target_col = num_cols[0]
        y = df[target_col].values
        
        method = "Simple Linear Regression"
        confidence_val = "Medium"
        
        variance = np.std(y) / np.mean(y) if np.mean(y) != 0 else 0
        
        if len(y) < 5:
            method = "Simple Moving Average"
            prediction = np.mean(y[-3:])
            confidence_val = "Low (Small Dataset)"
        elif variance > 1.0:
            method = "Weighted Moving Average"
            weights = np.arange(1, len(y) + 1)
            prediction = np.average(y, weights=weights)
            confidence_val = "Low (High Volatility)"
        else:
            if time_col:
                df = df.sort_values(by=time_col)
                X = df[time_col].apply(lambda x: x.toordinal()).values.reshape(-1, 1)
            else:
                X = np.arange(len(df)).reshape(-1, 1)
                
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(X, y)
            
            if time_col:
                avg_delta = np.mean(np.diff(X.flatten())) if len(X) > 1 else 1
                next_x = X[-1] + (avg_delta if avg_delta > 0 else 1)
            else:
                next_x = np.array([[len(df)]])
                
            prediction = model.predict(next_x.reshape(-1, 1))[0]
            confidence_val = "High" if len(y) > 10 and variance < 0.2 else "Medium"

        metric = context.get("target_metric", target_col) if context else target_col
        entity = context.get("entity_type", "") if context else ""
        time_dim = context.get("time_dimension", "") if context else ""
        filters = context.get("filters", "") if context else ""

        time_phrase = f"next {time_dim}" if time_dim else "the next period"
        entity_phrase = f"for {entity}" if entity else ""
        filter_phrase = f" ({filters})" if filters else ""

        semantic_msg = f"Based on historical data, the {metric} {entity_phrase}{filter_phrase} is expected to be approximately {prediction:.2f} {time_phrase}."
        
        if confidence_val.startswith("Low"):
            semantic_msg = f"Historical data suggests {metric} {entity_phrase} might reach {prediction:.2f}, but current trends are inconsistent."

        return {
            "target": target_col,
            "current_last": float(y[-1]),
            "predicted_next": float(prediction),
            "confidence": confidence_val,
            "method": method,
            "message": semantic_msg,
            "context": context,
            "why": f"This prediction uses {method} because the data has {('high' if variance > 0.5 else 'stable')} variance and {len(y)} data points."
        }
        
    except Exception as e:
        logger.error(f"Error in prediction: {e}")
        return {"error": f"Forecasting failed to find a stable pattern."}
