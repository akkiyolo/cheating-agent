import { Link } from "react-router-dom";
import Layout from "../components/Layout";

export default function Submitted() {
  return (
    <Layout>
      <div className="mx-auto mt-12 max-w-md space-y-4 rounded-lg bg-white p-6 text-center shadow">
        <h1 className="text-xl font-semibold">Assessment submitted</h1>
        <p className="text-slate-600">Your answers have been recorded and graded.</p>
        <Link
          to="/results"
          className="inline-block rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          View results
        </Link>
      </div>
    </Layout>
  );
}
