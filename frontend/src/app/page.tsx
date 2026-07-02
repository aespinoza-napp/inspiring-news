import React from 'react';

export default async function Dashboard() {
  const stats = await fetch('http://localhost:8000/api/health').then(res => res.json());

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold">News Intel Dashboard</h1>
      <div className="mt-4 p-4 border rounded shadow">
        <p>System Status: <span className={stats.status === 'ok' ? 'text-green-500' : 'text-red-500'}>{stats.status}</span></p>
        <p>Database: {stats.db_connection}</p>
      </div>
      {/* Add logic to list articles from Neo4j here */}
    </div>
  );
}