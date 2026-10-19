import type {RequestOptions,ApiResult} from './contracts';
export class ApiError extends Error {kind:string;status:number;retryAfter?:number;constructor(kind:string,status?:number)}
export function requestJson<T=unknown>(path:string,options?:RequestOptions):Promise<ApiResult<T>>;
export function postJson<T=unknown>(path:string,payload:unknown):Promise<ApiResult<T>>;
export function universityEmail(value:string):string|null;
export function retryGuidance(error:ApiError):string;
