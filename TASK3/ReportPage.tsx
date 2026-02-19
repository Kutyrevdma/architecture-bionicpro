import React, { useState } from 'react';

interface ReportItem {
  date: string;
  avg_signal: number;
  min_battery: number;
  total_actions: number;
}

interface ReportData {
  user_id: string;
  reports: ReportItem[];
}

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      // 1. Call BFF
      const response = await fetch(`http://localhost:8000/reports`, {
        credentials: 'include'
      });

      if (!response.ok) {
        if (response.status === 401) {
            window.location.reload();
            return;
        }
        throw new Error('Failed to fetch report metadata');
      }

      const data = await response.json();

      // 2. Check for CDN URL
      if (data.report_url) {
          console.log("Fetching from CDN: " + data.report_url);
          const cdnResponse = await fetch(data.report_url);
          if (!cdnResponse.ok) {
              throw new Error('Failed to fetch report from CDN');
          }
          const cdnData = await cdnResponse.json();
          setReportData(cdnData);
      }
      // Fallback for legacy format
      else if (data.reports) {
          setReportData(data);
      } else {
          alert(JSON.stringify(data));
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-4xl">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 mb-4 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Get Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportData && (
            <div className="mt-6">
                <h2 className="text-xl font-semibold mb-2">Report for {reportData.user_id}</h2>
                <div className="overflow-x-auto">
                    <table className="min-w-full bg-white border border-gray-300">
                        <thead>
                            <tr className="bg-gray-200">
                                <th className="py-2 px-4 border-b">Date</th>
                                <th className="py-2 px-4 border-b">Avg Signal</th>
                                <th className="py-2 px-4 border-b">Min Battery</th>
                                <th className="py-2 px-4 border-b">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reportData.reports.map((item, index) => (
                                <tr key={index} className="hover:bg-gray-100">
                                    <td className="py-2 px-4 border-b text-center">{item.date}</td>
                                    <td className="py-2 px-4 border-b text-center">{item.avg_signal.toFixed(2)}</td>
                                    <td className="py-2 px-4 border-b text-center">{item.min_battery}%</td>
                                    <td className="py-2 px-4 border-b text-center">{item.total_actions}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
