import logging
import time
from src.models_db import Job, JobStatus

from src import database
from src.services.processor import processor_service

logger = logging.getLogger("job_processor")

class JobProcessor:
    def process_job(self, job: Job):
        """
        Main entry point for processing a job.
        Routes to specific handlers based on job.type.
        """
        logger.info(f"⚙️ Processing Job {job.id} [Type: {job.type}]")
        
        # 0. Guardrails / Limits Check (MVP: Simple placeholder or ENV limit)
        if not self._check_limits(job):
            job.status = JobStatus.FAILED
            job.error_log = "Quota Exceeded (Guardrail)"
            logger.warning(f"⛔ Job {job.id} blocked by Guardrails.")
            # Early commit handled by finally block? No, finally block uses `job` status set here.
            # But process_job calls logic then sets COMPLETED.
            # We need to return early.
            # Let's adjust logic flow below.
            
            # Simple fix: Raise exception to go to Except block?
            # Or handle explicitly.
            # Raising exception is cleanest for current flow.
            raise ValueError("Quota Exceeded (Guardrail)")

        start_time = time.time()
        
        try:
            # Dispatcher
            job.status = JobStatus.PROCESSING
            database.db_session.commit() # Intermediary save for visibility

            if job.type == "TEST_JOB":
                result = self._handle_test_job(job)
            elif job.type == "PROCESS_REPORT":
                result = self._handle_process_report(job)
            elif job.type == "CHECK_DRIVE_CHANGES":
                result = self._handle_check_drive_changes(job)
            else:
                raise ValueError(f"Unknown Job Type: {job.type}")
                
            # Success
            job.status = JobStatus.COMPLETED
            job.result_payload = result
            logger.info(f"✅ Job {job.id} COMPLETED successfully.")
            
        except Exception as e:
            # Failure
            job.status = JobStatus.FAILED
            job.error_log = f"{type(e).__name__}: {str(e)}"
            logger.error(f"❌ Job {job.id} FAILED: {e}")
            job.attempts += 1 

            # Update Inspection Status to REJECTED if it was a PROCESS_REPORT job
            if job.type == "PROCESS_REPORT" and job.input_payload:
                file_id = job.input_payload.get('file_id')
                if file_id:
                    try:
                        from src.models_db import Inspection, InspectionStatus
                        inspection = database.db_session.query(Inspection).filter_by(drive_file_id=file_id).first()
                        if inspection:
                            inspection.status = InspectionStatus.REJECTED
                    except Exception as insp_err:
                        logger.error(f"Failed to update inspection status: {insp_err}")
            
        finally:
            # Metrics
            end_time = time.time()
            job.execution_time_seconds = end_time - start_time
            job.finished_at = database.db_session.query(Job).with_session(database.db_session).statement.compile().params.get('now') # Use datetime.utcnow() normally, keeping simple
            import datetime
            job.finished_at = datetime.datetime.utcnow()
            
            # Commit handled by caller? Or here? 
            # Typically easier to commit here to ensure status save.
            try:
                database.db_session.commit()
            except Exception as e:
                logger.error(f"FATAL: Failed to save job status: {e}")
                database.db_session.rollback()

    def _handle_test_job(self, job: Job) -> dict:
        """
        Simulates work.
        """
        delay = job.input_payload.get("delay", 1) if job.input_payload else 1
        logger.info(f"Sleeping for {delay} seconds...")
        time.sleep(delay)
        return {"message": "Test executed successfully", "original_delay": delay}

    def _handle_process_report(self, job: Job) -> dict:
        """
        Delegates to existing ProcessorService to analyze PDF and generate plan.
        Payload expected: {'file_id': str, 'filename': str}
        """
        payload = job.input_payload or {}
        file_id = payload.get('file_id')
        filename = payload.get('filename')
        
        logger.info(f"📄 Processing Report: {filename} (ID: {file_id})")
        
        if not file_id or not filename:
            raise ValueError("Missing file_id or filename in job payload")
            
        try:
            # Extract context
            est_id = payload.get('establishment_id')
            est_uuid = None
            if est_id:
                import uuid
                try: est_uuid = uuid.UUID(est_id)
                except: pass
            
            logger.info(f"🏭 Setup Context: Company={job.company_id}, Est={est_uuid}")

            result = processor_service.process_single_file(
                {'id': file_id, 'name': filename}, 
                company_id=job.company_id, # Tenant Context
                establishment_id=est_uuid,
                job=job
            )
            
            logger.info("✅ processor_service returned successfully.")

            # Usage is already updated inside process_single_file(job=job)
            # We can still log for confirmation
            logger.info(f"💰 Costs summary: In={job.cost_tokens_input} (${job.cost_input_usd:.6f}), Out={job.cost_tokens_output} (${job.cost_output_usd:.6f})")
            
            return {
                "status": "Processed via ProcessorService", 
                "file_id": file_id,
                "output_link": result.get('output_link') if result else None
            }
        except Exception as e:
            logger.error(f"❌ ProcessorService failed: {e}", exc_info=True)
            raise e

    def _handle_check_drive_changes(self, job: Job) -> dict:
        """
        Scans Drive folder for new files and processes them.
        """
        logger.info("📂 Checking Drive for changes via ProcessorService...")
        try:
            # Reuses existing logic to scan and process
            # Note: process_pending_files creates its own internal jobs or processes inline?
            # Creating internal jobs would be better for distinct tracking.
            # processor_service.process_pending_files() currently does logic inline or calling process_single_file.
            # Let's blindly trust it for MVP phase 2 async wrapper.
            
            processed_count = processor_service.process_pending_files()
            
            logger.info(f"✅ Drive Check Completed. Processed {processed_count} files.")
            return {"status": "Drive Check Completed", "processed_count": processed_count}
        except Exception as e:
            logger.error(f"❌ Drive Check Failed: {e}", exc_info=True)
            raise e

    def _check_limits(self, job: Job) -> bool:
        return True

job_processor = JobProcessor()
