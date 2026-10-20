/** PostgreSQL bigint identifiers are JSON integers; current UI accepts safe positive integers only. */
export type Id=number;
export type Price=string;
export type CategoryId=1|2|3|4|5;
export type ListingState='pending'|'active'|'sold'|'rejected'|'removed';
export type ReportReason='spam'|'prohibited_items'|'misleading_information';
export interface SessionUser {id:Id;email:string;verified:true;is_admin:boolean}
export interface AccessGrant {access_token:string;token_type:'bearer';expires_in:900}
export interface Contact {name:string|null;phone:string|null;telegram_username:string|null;external_contact_url:string|null}
export interface Profile extends Contact {id:Id;email:string;verified:true}
export interface Photo {id:Id;position:number;is_main:boolean;url:string}
export interface Category {id:1|2|3|4|5;key:string;label:string}
export interface ListingCard {id:Id;title:string;price:Price;currency:'KZT';category_id:CategoryId;condition:'new'|'used';published_at:string;main_photo:Photo|null}
export interface ListingDetail extends Omit<ListingCard,'main_photo'> {description:string;photos:Photo[];seller:Contact}
export interface OwnListing extends Omit<ListingDetail,'seller'|'published_at'> {status:ListingState;created_at:string;published_at:string|null;rejection_reason:string|null}
export interface Page<T> {items:T[];total:number;count:number;limit:number;offset:number}
export interface AdminUser {id:Id;email:string;name:string|null;role:'student'|'admin';verified:boolean;suspended:boolean;created_at:string}
export interface AdminListing extends Omit<OwnListing,'photos'> {seller:{id:Id;email:string;name:string|null};photos?:Photo[]}
export interface Report {id:Id;reason:ReportReason;created_at:string;reviewed_at:string|null;listing:{id:Id;title:string;status:ListingState;url:string}}
export interface RequestOptions {method?:string;payload?:unknown;body?:BodyInit;responseType?:'blob';headers?:Record<string,string>}
export interface ApiResult<T> {status:number;data:T;retryAfter:number}
export type Transport=(url:string,options?:RequestInit)=>Promise<Response>;

/** Manual action/upload results in canonical OpenAPI; no fields on listing/admin empty actions. */
export type EmptyAction=Record<string,never>;
export interface CreatedPhoto extends Photo {listing_id:Id}
export interface CleanupResult {cleanup_pending:boolean}
export interface AccountDeleted extends CleanupResult {deleted:true}
export interface ListingDeleted extends AccountDeleted {id:Id}
export interface ListingDecision {id:Id;status:'active'|'rejected';published_at:string|null;rejection_reason:string|null}
export interface SoldResult {id:Id;status:'sold';published_at:string|null}
export interface RemovedResult {id:Id;status:'removed';published_at:string|null}
export interface ReviewedResult {id:Id;reviewed_at:string}
export interface SafeError {detail:string}
