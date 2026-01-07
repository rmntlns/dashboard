import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Advanced PCA Visualization Dashboard",
    page_icon="📊",
    layout="wide"
)

@st.cache_data
def get_chunks_data():
    """Fetch all chunks from MongoDB"""
    try:
        # Get MongoDB connection details from environment variables
        mongo_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MONGODB_DATABASE")
        chunks_collection_name = os.getenv("MONGODB_CHUNKS_COLLECTION", "chunks")

        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[chunks_collection_name]

        # Fetch all records
        records = list(collection.find())

        # Convert to DataFrame
        if records:
            df = pd.DataFrame(records)
            # Convert ObjectId to string if present
            if '_id' in df.columns:
                df['_id'] = df['_id'].astype(str)
            return df
        else:
            return pd.DataFrame()

    except Exception as e:
        st.error(f"Error connecting to MongoDB chunks collection: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=60)  # Cache for 60 seconds to allow dynamic updates
def get_retrieval_logs(start_date=None, end_date=None, chunk_ids=None):
    """Fetch retrieval logs from MongoDB with optional filters"""
    try:
        # Get MongoDB connection details from environment variables
        mongo_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MONGODB_DATABASE")
        logs_collection_name = os.getenv("MONGODB_LOGS_COLLECTION", "retrieval_logs")

        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[logs_collection_name]

        # Build query filter
        query = {}
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date.isoformat()
            if end_date:
                query['timestamp']['$lte'] = end_date.isoformat()

        if chunk_ids:
            query['chunk_id'] = {'$in': chunk_ids}

        # Fetch records
        records = list(collection.find(query))

        # Convert to DataFrame
        if records:
            df = pd.DataFrame(records)
            # Convert ObjectId to string if present
            if '_id' in df.columns:
                df['_id'] = df['_id'].astype(str)
            # Convert timestamp to datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return pd.DataFrame()

    except Exception as e:
        st.error(f"Error connecting to MongoDB retrieval_logs collection: {str(e)}")
        return pd.DataFrame()

def calculate_usage_counts(chunks_df, logs_df):
    """Calculate usage count for each chunk based on retrieval logs"""
    if logs_df.empty:
        chunks_df['usage_count'] = 0
        return chunks_df

    # Count occurrences of each chunk_id in logs
    usage_counts = logs_df['chunk_id'].value_counts().to_dict()

    # Map usage counts to chunks
    chunks_df['usage_count'] = chunks_df['id'].map(usage_counts).fillna(0).astype(int)

    return chunks_df

def get_lifetime_usage_count(chunk_id):
    """Get lifetime (all-time) usage count for a specific chunk"""
    try:
        mongo_uri = os.getenv("MONGODB_URI")
        database_name = os.getenv("MONGODB_DATABASE")
        logs_collection_name = os.getenv("MONGODB_LOGS_COLLECTION", "retrieval_logs")

        client = MongoClient(mongo_uri)
        db = client[database_name]
        collection = db[logs_collection_name]

        count = collection.count_documents({'chunk_id': chunk_id})
        return count
    except Exception as e:
        st.error(f"Error getting lifetime usage count: {str(e)}")
        return 0

def main():
    st.title("📊 Advanced PCA Visualization Dashboard")

    # Instructions
    with st.expander("ℹ️ How to use this dashboard"):
        st.markdown("""
        **Interactive Features:**
        1. **Date Filter**: Select time range to analyze usage patterns
        2. **Area Selection**: Use box/lasso/point selection to explore chunks
        3. **Dynamic Metrics**: View aggregate statistics or individual chunk details

        **Chart Selection Modes:**
        - 📦 **Box Select**: Click and drag to draw a rectangle around points
        - 🎯 **Lasso Select**: Use the lasso tool in the toolbar to draw custom shapes around points
        - 🔘 **Point Select**: Click individual points to select them
        - 🔄 **Pan**: Use pan mode to navigate the chart without selecting
        - 🔍 **Zoom**: Use zoom tools to focus on specific areas (default mode)
        """)

    # Initialize session state
    if 'date_filter' not in st.session_state:
        st.session_state.date_filter = 'all_time'
    if 'custom_start_date' not in st.session_state:
        st.session_state.custom_start_date = None
    if 'custom_end_date' not in st.session_state:
        st.session_state.custom_end_date = None

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Refresh data button
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # Load chunks data
    with st.spinner("Loading chunks from MongoDB..."):
        chunks_df = get_chunks_data()

    if chunks_df.empty:
        st.error("No chunks found or connection failed. Please check your MongoDB configuration.")
        st.info("Make sure to set these environment variables in your .env file:")
        st.code("""
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=your_database_name
MONGODB_CHUNKS_COLLECTION=chunks
MONGODB_LOGS_COLLECTION=retrieval_logs
        """)
        return

    # Check if required columns exist
    if 'Xpca' not in chunks_df.columns or 'Ypca' not in chunks_df.columns:
        st.error("Required columns 'Xpca' and 'Ypca' not found in the data.")
        st.info("Available columns:")
        st.write(chunks_df.columns.tolist())
        return

    # Add data summary to sidebar
    with st.sidebar:
        st.subheader("📋 Data Summary")
        st.metric("Total Chunks", len(chunks_df))
    
    # Date Range Filter
    st.subheader("📅 Date Range Filter")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        if st.button("All Time", use_container_width=True, type="primary" if st.session_state.date_filter == 'all_time' else "secondary"):
            st.session_state.date_filter = 'all_time'
            st.rerun()
    with col2:
        if st.button("Last 24h", use_container_width=True, type="primary" if st.session_state.date_filter == '24h' else "secondary"):
            st.session_state.date_filter = '24h'
            st.rerun()
    with col3:
        if st.button("Last 7 days", use_container_width=True, type="primary" if st.session_state.date_filter == '7d' else "secondary"):
            st.session_state.date_filter = '7d'
            st.rerun()
    with col4:
        if st.button("Last 30 days", use_container_width=True, type="primary" if st.session_state.date_filter == '30d' else "secondary"):
            st.session_state.date_filter = '30d'
            st.rerun()
    with col5:
        if st.button("Last 90 days", use_container_width=True, type="primary" if st.session_state.date_filter == '90d' else "secondary"):
            st.session_state.date_filter = '90d'
            st.rerun()
    with col6:
        if st.button("Custom", use_container_width=True, type="primary" if st.session_state.date_filter == 'custom' else "secondary"):
            st.session_state.date_filter = 'custom'
            st.rerun()

    # Custom date picker
    start_date = None
    end_date = None

    if st.session_state.date_filter == 'custom':
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Start Date", value=st.session_state.custom_start_date)
            st.session_state.custom_start_date = start_date
        with col_end:
            end_date = st.date_input("End Date", value=st.session_state.custom_end_date)
            st.session_state.custom_end_date = end_date

        if start_date:
            start_date = datetime.combine(start_date, datetime.min.time())
        if end_date:
            end_date = datetime.combine(end_date, datetime.max.time())
    elif st.session_state.date_filter == '24h':
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)
    elif st.session_state.date_filter == '7d':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
    elif st.session_state.date_filter == '30d':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
    elif st.session_state.date_filter == '90d':
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

    # Load retrieval logs based on date filter
    with st.spinner("Loading retrieval logs..."):
        logs_df = get_retrieval_logs(start_date, end_date)

    # Calculate usage counts based on filtered logs
    chunks_df = calculate_usage_counts(chunks_df, logs_df)

    # Scatterplot - Full width
    st.subheader("🎯 Interactive PCA Scatterplot")

    # Prepare hover data - truncate long text for better display
    df_plot = chunks_df.copy()
    df_plot['question_short'] = df_plot['question'].apply(lambda x: str(x)[:100] + '...' if len(str(x)) > 100 else str(x))
    df_plot['answer_short'] = df_plot['answer'].apply(lambda x: str(x)[:100] + '...' if len(str(x)) > 100 else str(x))

    # Create Plotly scatterplot with color coding based on usage_count
    fig = px.scatter(
        df_plot,
        x='Xpca',
        y='Ypca',
        color='usage_count',
        color_continuous_scale=['#808080', '#00FF00'],  # Gray to bright green
        title="PCA Coordinates Scatterplot (Color: Usage Count)",
        labels={
            'Xpca': 'X PCA',
            'Ypca': 'Y PCA',
            'usage_count': 'Usage Count'
        },
        hover_data={
            'Xpca': ':.4f',
            'Ypca': ':.4f',
            'id': True,
            'usage_count': True,
            'question_short': True,
            'answer_short': True
        },
        custom_data=['id', 'usage_count', 'question_short', 'answer_short']
    )

    # Update hover template for better formatting
    fig.update_traces(
        hovertemplate='<b>Chunk ID:</b> %{customdata[0]}<br>' +
                      '<b>Usage Count:</b> %{customdata[1]}<br>' +
                      '<b>X PCA:</b> %{x:.4f}<br>' +
                      '<b>Y PCA:</b> %{y:.4f}<br>' +
                      '<b>Question:</b> %{customdata[2]}<br>' +
                      '<b>Answer:</b> %{customdata[3]}<br>' +
                      '<extra></extra>'
    )

    # Update layout for better interactivity
    fig.update_layout(
        height=600,
        dragmode='zoom',  # Enable zoom as default tool
        selectdirection='d',  # 'd' for diagonal selection
        title_x=0.5,
        title_font_size=16,
        coloraxis_colorbar=dict(
            title="Usage Count",
            thicknessmode="pixels",
            thickness=15,
            lenmode="pixels",
            len=200
        )
    )

    # Update traces for better selection visibility
    fig.update_traces(
        marker=dict(size=6),
        selected=dict(marker=dict(opacity=1.0, size=8)),
        unselected=dict(marker=dict(opacity=0.3, size=4))
    )
    
    # Display the chart with selection events
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        key="pca_chart",
        on_select="rerun",
        selection_mode=['box', 'lasso', 'points']
    )

    # Handle selection events and determine state
    selected_chunk_indices = []
    selected_chunks = []

    if event and event.selection and event.selection.points:
        # Handle point selections
        points = event.selection.points
        if points:
            selected_chunk_indices = [point['point_index'] for point in points]
            selected_chunks = [chunks_df.iloc[idx] for idx in selected_chunk_indices if idx < len(chunks_df)]

    # Determine which state we're in
    num_selected = len(selected_chunks)

    st.markdown("---")

    # Dynamic Content Section based on selection state
    if num_selected == 0:
        # STATE 1: No Selection - Show aggregate metrics
        display_aggregate_metrics(logs_df, "All Chunks")

    elif num_selected == 1:
        # STATE 3: Single Chunk Selected - Show chunk details and retrieval logs
        chunk = selected_chunks[0]
        chunk_id = chunk.get('id', 'N/A')

        # Section 1: Aggregate Metrics (in expander, collapsed)
        chunk_logs = logs_df[logs_df['chunk_id'] == chunk_id] if not logs_df.empty else pd.DataFrame()

        with st.expander("📊 Aggregate Metrics for This Chunk", expanded=False):
            # Display metrics without nested expander
            if chunk_logs.empty:
                st.info("No retrieval logs found for this time period")
            else:
                # Metric cards
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Total User Queries", len(chunk_logs))

                with col2:
                    avg_score = chunk_logs['similarity_score'].mean() if 'similarity_score' in chunk_logs.columns else 0
                    st.metric("Average Similarity Score", f"{avg_score:.4f}")

                # Similarity score distribution histogram
                st.subheader("Similarity Score Distribution")

                if 'similarity_score' in chunk_logs.columns:
                    # Create bins
                    bins = [0, 0.6, 0.7, 0.8, 0.9, 1.0]
                    labels = ['<0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0']

                    chunk_logs_copy = chunk_logs.copy()
                    chunk_logs_copy['score_bucket'] = pd.cut(chunk_logs_copy['similarity_score'], bins=bins, labels=labels, include_lowest=True)
                    bucket_counts = chunk_logs_copy['score_bucket'].value_counts().reindex(labels, fill_value=0)

                    # Create histogram
                    fig_hist = go.Figure(data=[
                        go.Bar(
                            x=labels,
                            y=bucket_counts.values,
                            marker_color='#1f77b4'
                        )
                    ])

                    fig_hist.update_layout(
                        xaxis_title="Similarity Score Range",
                        yaxis_title="Count of Retrievals",
                        height=400,
                        showlegend=False
                    )

                    st.plotly_chart(fig_hist, use_container_width=True)
                else:
                    st.warning("No similarity_score data available")

        # Section 2: Chunk Details (expanded)
        st.subheader("📋 Chunk Details")
        display_chunk_info_card(chunk, get_lifetime_usage_count(chunk_id))

        # Retrieval Logs Table
        st.subheader("📜 Retrieval Logs")
        display_retrieval_logs_table(chunk_id, start_date, end_date)

    else:
        # STATE 2: Multiple Chunks Selected - Show filtered aggregate metrics
        selected_chunk_ids = [chunk.get('id') for chunk in selected_chunks]
        filtered_logs = logs_df[logs_df['chunk_id'].isin(selected_chunk_ids)] if not logs_df.empty else pd.DataFrame()
        display_aggregate_metrics(filtered_logs, f"{num_selected} Selected Chunks")
    
def display_aggregate_metrics(logs_df, title):
    """Display aggregate metrics for retrieval logs"""
    with st.expander(f"� Aggregate Metrics - {title}", expanded=True):
        if logs_df.empty:
            st.info("No retrieval logs found for this time period")
            return

        # Metric cards
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Total User Queries", len(logs_df))

        with col2:
            avg_score = logs_df['similarity_score'].mean() if 'similarity_score' in logs_df.columns else 0
            st.metric("Average Similarity Score", f"{avg_score:.4f}")

        # Similarity score distribution histogram
        st.subheader("Similarity Score Distribution")

        if 'similarity_score' in logs_df.columns:
            # Create bins
            bins = [0, 0.6, 0.7, 0.8, 0.9, 1.0]
            labels = ['<0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0']

            logs_df['score_bucket'] = pd.cut(logs_df['similarity_score'], bins=bins, labels=labels, include_lowest=True)
            bucket_counts = logs_df['score_bucket'].value_counts().reindex(labels, fill_value=0)

            # Create histogram
            fig_hist = go.Figure(data=[
                go.Bar(
                    x=labels,
                    y=bucket_counts.values,
                    marker_color='#1f77b4'
                )
            ])

            fig_hist.update_layout(
                xaxis_title="Similarity Score Range",
                yaxis_title="Count of Retrievals",
                height=400,
                showlegend=False
            )

            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.warning("No similarity_score data available")

def display_chunk_info_card(chunk, lifetime_usage):
    """Display detailed chunk information card"""
    chunk_id = chunk.get('id', 'N/A')

    st.markdown(f"""
    <div style="background-color: #f0f2f6; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #00FF00;">
        <p style="margin: 0; font-size: 14px; font-weight: 600; color: #1f77b4;">🔖 Chunk ID: {chunk_id}</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📍 PCA Coordinates**")
        st.write(f"• X: `{chunk.get('Xpca', 'N/A'):.6f}`")
        st.write(f"• Y: `{chunk.get('Ypca', 'N/A'):.6f}`")

    with col2:
        st.markdown("**📊 Lifetime Usage Count**")
        st.markdown(f"<h2 style='color: #00FF00; margin: 0;'>{lifetime_usage}</h2>", unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("**❓ Question**")
    st.info(chunk.get('question', 'N/A'))

    st.markdown("**💡 Answer**")
    st.success(chunk.get('answer', 'N/A'))

def display_retrieval_logs_table(chunk_id, start_date, end_date):
    """Display paginated retrieval logs table for a specific chunk"""
    # Initialize pagination state
    if 'logs_page' not in st.session_state:
        st.session_state.logs_page = 0

    # Get logs for this chunk
    logs_df = get_retrieval_logs(start_date, end_date, [chunk_id])

    if logs_df.empty:
        st.info("No retrievals found for this chunk in the selected time period")
        return

    # Sort by timestamp (most recent first) by default
    logs_df = logs_df.sort_values('timestamp', ascending=False)

    # Pagination
    page_size = 10
    total_pages = (len(logs_df) - 1) // page_size + 1
    start_idx = st.session_state.logs_page * page_size
    end_idx = min(start_idx + page_size, len(logs_df))

    # Display table
    display_logs = logs_df.iloc[start_idx:end_idx][['timestamp', 'user_query', 'similarity_score']].copy()
    display_logs['timestamp'] = display_logs['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

    st.dataframe(
        display_logs,
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": st.column_config.TextColumn("Timestamp", width="medium"),
            "user_query": st.column_config.TextColumn("User Query", width="large"),
            "similarity_score": st.column_config.NumberColumn("Similarity Score", format="%.4f", width="small")
        }
    )

    # Pagination controls
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("⬅️ Previous", disabled=(st.session_state.logs_page == 0)):
            st.session_state.logs_page -= 1
            st.rerun()

    with col2:
        st.markdown(f"<p style='text-align: center;'>Page {st.session_state.logs_page + 1} of {total_pages} ({len(logs_df)} total records)</p>", unsafe_allow_html=True)

    with col3:
        if st.button("Next ➡️", disabled=(st.session_state.logs_page >= total_pages - 1)):
            st.session_state.logs_page += 1
            st.rerun()

if __name__ == "__main__":
    main()