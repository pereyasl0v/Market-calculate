import {NextResponse} from "next/server";
// Server-side same-origin proxy: keeps browser requests on the Next.js origin.
export async function GET(request) {
 const query = new URL(request.url).searchParams.get("query");
 if (!query || query.trim().length < 2 || query.length > 150) return NextResponse.json({detail:"Query must be 2–150 chars"},{status:400});
 const base = process.env.BACKEND_URL || "http://localhost:8000";
 try {
   const response=await fetch(base+"/api/wb/search?query="+encodeURIComponent(query),{cache:"no-store",signal:AbortSignal.timeout(30000)});
   const body=await response.json();
   return NextResponse.json(body,{status:response.status,headers:{"Cache-Control":"no-store"}});
 } catch {
   return NextResponse.json({detail:"FastAPI недоступен. Проверьте BACKEND_URL и запущен ли backend."},{status:502});
 }
}
