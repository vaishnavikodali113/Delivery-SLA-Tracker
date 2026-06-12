# Deployment Guide: Option A (Vercel Frontend & Containerized Backend)

This guide walks you through deploying the **Delivery SLA & Data Quality Tracker** project using **Vercel** for the frontend dashboard and a container service like **Render** or **Railway** for the FastAPI backend.

---

## Step 1: Push the Project to GitHub
To deploy to both Vercel and Render/Railway, your project needs to be in a remote Git repository:

1. Create a new repository on [GitHub](https://github.com).
2. Initialize and push your local repository:
   ```bash
   git init
   git add .
   git commit -m "Configure deployment changes"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

---

## Step 2: Deploy the Backend on Render or Railway

We will deploy the backend as a container using the root [Dockerfile](file:///Users/srivaishnavikodali/Desktop/projects/Delivery%20SLA%20Tracker%20/Dockerfile).

### Option 2A: Using Render
1. Log in to [Render](https://render.com) and click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   * **Name**: `delivery-sla-backend`
   * **Language**: `Docker`
   * **Branch**: `main`
4. Under **Advanced Settings**:
   * Add a **Disk (Persistent Volume)**:
     * **Mount Path**: `/data`
     * **Size**: `1 GB` (or minimum size allowed)
   * Add the following **Environment Variables**:
     * `SQLITE_DB_PATH` = `/data/delivery_oltp.db`
     * `DUCKDB_PATH` = `/data/delivery_warehouse.db`
5. Click **Create Web Service**. 
6. Note down the deployed service URL (e.g., `https://delivery-sla-backend.onrender.com`).

### Option 2B: Using Railway
1. Log in to [Railway](https://railway.app) and click **New Project** > **Deploy from GitHub repo**.
2. Select your repository.
3. Under **Variables**, add:
   * `SQLITE_DB_PATH` = `/data/delivery_oltp.db`
   * `DUCKDB_PATH` = `/data/delivery_warehouse.db`
4. Under **Settings**:
   * Add a **Volume Mount**:
     * **Mount Path**: `/data`
5. Note down your public URL generated under **Networking**.

---

## Step 3: Deploy the Frontend on Vercel

1. Log in to [Vercel](https://vercel.com) and click **Add New** > **Project**.
2. Import your GitHub repository.
3. Configure the build settings:
   * **Framework Preset**: `Vite` (Vercel should automatically detect this)
   * **Root Directory**: `frontend` (Click **Edit** next to Root Directory and select the `frontend` folder)
4. Under **Environment Variables**, add:
   * **Key**: `VITE_API_BASE_URL`
   * **Value**: *Your deployed backend URL from Step 2* (e.g., `https://delivery-sla-backend.onrender.com`)
5. Click **Deploy**.

---

## Step 4: Verification
1. Open your deployed Vercel URL in your browser.
2. Verify that the dashboard is fetching data from the backend by starting the simulator or running a sync using the **Sync Now** button.
3. Reload the dashboard or trigger a backend redeployment and ensure your analytics data remains intact (verifying that the persistent volume mount in Render/Railway is correctly preserving the databases).
