import React from 'react';
// Shared presentation only: field values, validation and requests stay in their feature components.
export function FormIntro({title,children}){return <div className="form-intro"><h2>{title}</h2>{children&&<p>{children}</p>}</div>;}
