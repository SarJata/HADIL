import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

from ai_modules.context_analyzer import extract_query_context

def generate_insights(data: List[Dict[str, Any]], query: Optional[str] = None, sql: Optional[str] = None) -> List[str]:
    if not data:
        return ["No data available to generate insights."]
    
    try:
        df = pd.DataFrame(data)
        insights = []
        context = extract_query_context(query, sql) if query and sql else None

        # 1. Detect Column Types
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        # Attempt to find time columns
        time_cols = []
        for col in cat_cols:
            if any(word in col.lower() for word in ['date', 'time', 'created', 'year', 'month']):
                try:
                    df[col] = pd.to_datetime(df[col])
                    time_cols.append(col)
                except: pass
        
        cat_cols = [c for c in cat_cols if c not in time_cols]

        # 2. Semantic Mapping
        metric_label = context.get("target_metric") if context else None
        entity_label = context.get("entity_type") if context else None

        # 3. Numeric Insights (Context-Aware)
        for col in num_cols:
            mean_val = df[col].mean()
            max_val = df[col].max()
            label = metric_label if metric_label and col.lower() in metric_label.lower() else col
            
            insights.append(f"Average {label} is {mean_val:.2f}.")
            insights.append(f"The highest recorded {label} is {max_val:.2f}.")
            
            if len(df) > 1:
                std_dev = df[col].std()
                if std_dev > mean_val * 0.5:
                    insights.append(f"There is high variability in {label}, suggesting inconsistent results.")
                elif std_dev < mean_val * 0.1:
                    insights.append(f"The {label} appears to be very stable over time.")

        # 4. Categorical Insights
        for col in cat_cols:
            counts = df[col].value_counts()
            if not counts.empty:
                top_cat = counts.idxmax()
                top_count = counts.max()
                label = entity_label if entity_label and col.lower() in entity_label.lower() else col
                insights.append(f"'{top_cat}' is the most frequent {label} in this dataset.")

        # 5. Trend Insights
        if time_cols and num_cols:
            t_col = time_cols[0]
            n_col = num_cols[0]
            df_sorted = df.sort_values(by=t_col)
            
            if len(df_sorted) >= 2:
                diff = df_sorted[n_col].iloc[-1] - df_sorted[n_col].iloc[0]
                direction = "upward" if diff > 0 else "downward"
                insights.append(f"The trend for {n_col} shows a general {direction} movement.")

        return insights
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return [f"Analysis completed, but semantic insights could not be fully generated."]

def predict_trend(data: List[Dict[str, Any]], query: Optional[str] = None, sql: Optional[str] = None) -> Dict[str, Any]:
    if not data or len(data) < 3:
        return {"error": "Insufficient data for prediction (need at least 3 records)."}
    
    try:
        df = pd.DataFrame(data)
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        
        # Get Context
        context = extract_query_context(query, sql) if query and sql else None
        
        # Find time column
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
        
        # 1. Dynamic Model Selection
        method = "Simple Linear Regression"
        confidence_val = "Medium"
        
        # Check variance
        variance = np.std(y) / np.mean(y) if np.mean(y) != 0 else 0
        
        if len(y) < 5:
            # Too small for regression, use Moving Average
            method = "Simple Moving Average"
            prediction = np.mean(y[-3:])
            confidence_val = "Low (Small Dataset)"
        elif variance > 1.0:
            # Too noisy for linear trend
            method = "Weighted Moving Average"
            weights = np.arange(1, len(y) + 1)
            prediction = np.average(y, weights=weights)
            confidence_val = "Low (High Volatility)"
        else:
            # Linear trend
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

        # 2. Semantic Message Construction
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
