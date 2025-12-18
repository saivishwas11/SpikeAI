"""
SEO Agent for analyzing Screaming Frog SEO data.

This module provides functionality to analyze and query SEO data from
Screaming Frog exports using natural language queries.
"""
import re
import logging
from typing import Dict, Any, List, Optional, Union, Tuple
import pandas as pd
from pydantic import BaseModel, Field

from utils.llm_utils import LLMQueryPlanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM utilities
llm_utils = LLMQueryPlanner()

class SEOQueryPlan(BaseModel):
    """Schema for SEO query plans."""
    filters: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of filter conditions to apply to the data"
    )
    group_by: List[str] = Field(
        default_factory=list,
        description="List of columns to group by"
    )
    aggregations: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dictionary of column to aggregation functions to apply"
    )
    sort_by: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of columns to sort by with sort order"
    )
    limit: int = Field(
        default=100,
        description="Maximum number of results to return"
    )
    select_columns: List[str] = Field(
        default_factory=list,
        description="List of columns to include in the result"
    )


class SEOAgent:
    """Handles SEO data analysis from Screaming Frog exports."""
    
    def __init__(self):
        """Initialize the SEO agent."""
        self.df = None
        self.available_columns = []
    
    def load_data(self, df: pd.DataFrame) -> None:
        """
        Load SEO data into the agent.
        
        Args:
            df: Pandas DataFrame containing SEO data from Screaming Frog
        """
        self.df = df.copy()
        self.available_columns = list(df.columns)
        
        # Clean column names (remove any leading/trailing whitespace)
        self.df.columns = [col.strip() for col in self.df.columns]
        
        # Convert numeric columns to appropriate types
        self._convert_numeric_columns()
    
    def _convert_numeric_columns(self) -> None:
        """Convert columns that should be numeric to appropriate types."""
        if self.df is None:
            return
            
        # Common numeric column patterns in Screaming Frog
        numeric_patterns = [
            'length$', 'count$', 'size$', 'score$', 'depth$', 
            '^h[1-6]_count', 'word_count', 'links_', 'status_code',
            'inlinks', 'outlinks', 'size_bytes'
        ]
        
        for col in self.df.columns:
            # Skip non-string columns
            if not pd.api.types.is_string_dtype(self.df[col]):
                continue
                
            # Check if column matches any numeric pattern
            if any(re.search(pattern, col, re.IGNORECASE) for pattern in numeric_patterns):
                try:
                    # Try to convert to numeric, coerce errors to NaN
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                except (ValueError, TypeError):
                    continue
    
    def _parse_natural_language_query(self, query: str) -> SEOQueryPlan:
        """
        Parse a natural language query into a structured query plan.
        
        Args:
            query: Natural language query string
            
        Returns:
            SEOQueryPlan containing the parsed query parameters
        """
        system_prompt = """You are an expert at converting natural language questions about SEO data into structured queries.
        
        Your task is to analyze the user's question and extract the following information:
        
        1. Filters: Conditions to filter the data (e.g., "title length > 60", "status code is 404")
        2. Grouping: How to group the results (e.g., "group by status code")
        3. Aggregations: What to calculate for each group (e.g., "count URLs", "average word count")
        4. Sorting: How to sort the results (e.g., "sort by word count descending")
        5. Limit: Maximum number of results to return
        
        Return the response as a JSON object with the following structure:
        {
            "filters": [
                {"column": "column_name", "operator": "==|>|<|>=|<=", "value": "value"},
                ...
            ],
            "group_by": ["column1", "column2", ...],
            "aggregations": {"column_name": ["count", "sum", "mean", "min", "max"], ...},
            "sort_by": [{"column": "column_name", "order": "asc|desc"}, ...],
            "limit": 100,
            "select_columns": ["column1", "column2", ...]
        }
        
        Available columns in the data:
        {columns}
        
        Examples:
        
        1. Query: "Show me all pages with 4xx or 5xx status codes"
        Response:
        {{
            "filters": [
                {{"column": "Status Code", "operator": ">=", "value": 400}},
                {{"column": "Status Code", "operator": "<", "value": 600}}
            ],
            "select_columns": ["Address", "Status Code", "Title 1", "H1-1"]
        }}
        
        2. Query: "Group by status code and count the number of pages"
        Response:
        {{
            "group_by": ["Status Code"],
            "aggregations": {{"Address": ["count"]}},
            "select_columns": ["Status Code", "Address_count"],
            "sort_by": [{{"column": "Address_count", "order": "desc"}}]
        }}
        
        3. Query: "Show me pages with duplicate title tags"
        Response:
        {{
            "filters": [
                {{"column": "Title 1", "operator": "!=", "value": ""}},
                {{"column": "Title 1 Duplicate", "operator": "==", "value": True}}
            ],
            "select_columns": ["Address", "Title 1"],
            "sort_by": [{{"column": "Title 1", "order": "asc"}}]
        }}
        """.format(columns=", ".join(f'"{col}"' for col in self.available_columns))
        
        try:
            response = llm_utils.llm.completion(
                model="gemini-1.5-pro",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            # Parse the response
            import json
            plan_data = json.loads(response.choices[0].message.content)
            return SEOQueryPlan(**plan_data)
            
        except Exception as e:
            logger.error(f"Error parsing SEO query: {str(e)}")
            # Return a default plan if parsing fails
            return SEOQueryPlan()
    
    def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a natural language query against the SEO data.
        
        Args:
            query: Natural language query string
            
        Returns:
            Dict containing the query results and a natural language response
        """
        if self.df is None or self.df.empty:
            return {
                "answer": "No SEO data has been loaded. Please load data first.",
                "data": None
            }
        
        try:
            # Parse the natural language query
            plan = self._parse_natural_language_query(query)
            
            # Apply filters
            df_filtered = self._apply_filters(self.df, plan.filters)
            
            # Apply grouping and aggregation if specified
            if plan.group_by or plan.aggregations:
                result_df = self._apply_grouping(df_filtered, plan)
            else:
                result_df = df_filtered.copy()
            
            # Apply sorting
            if plan.sort_by:
                result_df = self._apply_sorting(result_df, plan.sort_by)
            
            # Apply limit
            if plan.limit and len(result_df) > plan.limit:
                result_df = result_df.head(plan.limit)
            
            # Select only the requested columns (if any)
            if plan.select_columns:
                # Only include columns that exist in the dataframe
                valid_columns = [col for col in plan.select_columns if col in result_df.columns]
                if valid_columns:
                    result_df = result_df[valid_columns]
            
            # Generate a natural language response
            answer = self._generate_response(query, result_df, len(df_filtered))
            
            return {
                "answer": answer,
                "data": result_df.to_dict(orient='records'),
                "query_plan": plan.dict()
            }
            
        except Exception as e:
            error_msg = f"Error executing SEO query: {str(e)}"
            logger.exception(error_msg)
            return {
                "answer": f"Sorry, I couldn't process your request. {error_msg}",
                "data": None,
                "error": str(e)
            }
    
    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict[str, Any]]) -> pd.DataFrame:
        """Apply filters to the dataframe."""
        if not filters:
            return df
            
        for filter_cond in filters:
            column = filter_cond.get('column')
            operator = filter_cond.get('operator', '==')
            value = filter_cond.get('value')
            
            if not column or column not in df.columns:
                continue
                
            try:
                if operator == '==':
                    df = df[df[column] == value]
                elif operator == '!=':
                    df = df[df[column] != value]
                elif operator == '>':
                    df = df[df[column] > value]
                elif operator == '>=':
                    df = df[df[column] >= value]
                elif operator == '<':
                    df = df[df[column] < value]
                elif operator == '<=':
                    df = df[df[column] <= value]
                elif operator.lower() == 'contains':
                    df = df[df[column].astype(str).str.contains(str(value), case=False, na=False)]
                elif operator.lower() == 'not contains':
                    df = df[~df[column].astype(str).str.contains(str(value), case=False, na=False)]
                elif operator.lower() == 'in':
                    if isinstance(value, list):
                        df = df[df[column].isin(value)]
                elif operator.lower() == 'not in':
                    if isinstance(value, list):
                        df = df[~df[column].isin(value)]
            except Exception as e:
                logger.warning(f"Error applying filter {column} {operator} {value}: {str(e)}")
                continue
                
        return df
    
    def _apply_grouping(self, df: pd.DataFrame, plan: SEOQueryPlan) -> pd.DataFrame:
        """Apply grouping and aggregation to the dataframe."""
        if not plan.group_by and not plan.aggregations:
            return df
            
        # Ensure group_by columns exist in the dataframe
        valid_group_columns = [col for col in plan.group_by if col in df.columns]
        
        # Prepare aggregations
        agg_dict = {}
        for col, funcs in plan.aggregations.items():
            if col in df.columns:
                for func in funcs:
                    if func.lower() in ['count', 'sum', 'mean', 'min', 'max', 'nunique']:
                        agg_dict[f"{col}_{func}"] = (col, func)
        
        # If no valid aggregations, just group and count
        if not agg_dict and valid_group_columns:
            result_df = df.groupby(valid_group_columns).size().reset_index(name='count')
        elif valid_group_columns:
            # Apply groupby with aggregations
            grouped = df.groupby(valid_group_columns)
            result_df = grouped.agg(**{k: v for k, v in agg_dict.items()}).reset_index()
        else:
            # No valid group columns, apply aggregations to the entire dataframe
            result_df = df.agg({col: func for col, func in agg_dict.values()}).to_frame().T
        
        return result_df
    
    def _apply_sorting(self, df: pd.DataFrame, sort_specs: List[Dict[str, str]]) -> pd.DataFrame:
        """Apply sorting to the dataframe."""
        if not sort_specs or df.empty:
            return df
            
        sort_columns = []
        sort_ascending = []
        
        for spec in sort_specs:
            column = spec.get('column')
            order = spec.get('order', 'asc').lower()
            
            if column in df.columns:
                sort_columns.append(column)
                sort_ascending.append(order == 'asc')
        
        if sort_columns:
            return df.sort_values(by=sort_columns, ascending=sort_ascending)
        
        return df
    
    def _generate_response(self, query: str, result_df: pd.DataFrame, total_filtered: int) -> str:
        """Generate a natural language response for the query results."""
        if result_df.empty:
            return "No results found matching your query."
            
        num_results = len(result_df)
        
        # Get a sample of the results for the LLM to analyze
        sample_size = min(5, num_results)
        sample_data = result_df.head(sample_size).to_dict(orient='records')
        
        # Generate a natural language summary using the LLM
        try:
            response = llm_utils.llm.completion(
                model="gemini-1.5-pro",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are an SEO expert analyzing website data. 
                        Provide a concise summary of the query results in 2-3 sentences. 
                        Highlight key findings and any potential issues."""
                    },
                    {
                        "role": "user", 
                        "content": f"Query: {query}\n\nResults (sample of {sample_size} out of {num_results}):\n{sample_data}"
                    }
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            summary = response.choices[0].message.content.strip()
            
            if total_filtered > num_results:
                summary += f"\n\nNote: Showing {num_results} of {total_filtered} total matching results."
                
            return summary
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return f"Found {num_results} results matching your query."


# Create a singleton instance
seo_agent = SEOAgent()


def run_seo_agent(query: str, df: pd.DataFrame = None) -> Dict[str, Any]:
    """
    Run the SEO agent with the given query and optional data.
    
    Args:
        query: Natural language query string
        df: Optional pandas DataFrame containing SEO data. If not provided, 
            the function will attempt to load it using utils.sheets.load_seo_data()
            
    Returns:
        Dict containing the query results and a natural language response
    """
    global seo_agent
    
    # Load data if not already loaded and df is provided
    if df is not None:
        seo_agent.load_data(df)
    elif seo_agent.df is None:
        # Try to load data using the sheets module
        try:
            from utils.sheets import load_seo_data
            df = load_seo_data()
            seo_agent.load_data(df)
        except Exception as e:
            return {
                "answer": f"Error loading SEO data: {str(e)}",
                "data": None,
                "error": str(e)
            }
    
    # Execute the query
    return seo_agent.execute_query(query)
