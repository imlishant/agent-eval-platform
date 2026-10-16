Title: Profile picture uploads fail with S3 AccessDenied
Severity: S3
### Impact
All users trying to upload a new profile picture since 09:02 get an error. Existing pictures still show.
### Repro
1. Log in as any user.
2. Go to Profile and upload a new picture.
3. The upload fails.
### Evidence
> 2026-10-01T09:02:11 ERROR UploadError: avatar upload failed user=7731 reason="S3 bucket avatars-prod: AccessDenied"
