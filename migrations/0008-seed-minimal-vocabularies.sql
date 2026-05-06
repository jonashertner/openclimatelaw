-- Minimum vocabulary seed for the Urgenda demo case + small margin for adjacent test cases.
-- Source = 'manual' because values are transcribed from Sabin's public taxonomy.
-- Plan 3+ will replace this with a bulk import from Sabin/CPR.

INSERT INTO vocabulary_jurisdiction (code, name, kind, source, source_version) VALUES
    ('NL', 'Netherlands', 'national', 'manual', 'plan-2-seed'),
    ('US', 'United States', 'national', 'manual', 'plan-2-seed'),
    ('DE', 'Germany',       'national', 'manual', 'plan-2-seed'),
    ('GB', 'United Kingdom', 'national', 'manual', 'plan-2-seed'),
    ('AU', 'Australia',     'national', 'manual', 'plan-2-seed'),
    ('BR', 'Brazil',        'national', 'manual', 'plan-2-seed'),
    ('ICJ',    'International Court of Justice',         'international', 'manual', 'plan-2-seed'),
    ('IACTHR', 'Inter-American Court of Human Rights',  'international', 'manual', 'plan-2-seed'),
    ('ECTHR',  'European Court of Human Rights',        'international', 'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_court (id, name, jurisdiction_code, level, source, source_version) VALUES
    ('nl-hoge-raad',           'Hoge Raad der Nederlanden (Supreme Court of the Netherlands)', 'NL', 'supreme',   'manual', 'plan-2-seed'),
    ('nl-hof-den-haag',        'Gerechtshof Den Haag (The Hague Court of Appeal)',             'NL', 'appellate', 'manual', 'plan-2-seed'),
    ('nl-rechtbank-den-haag',  'Rechtbank Den Haag (The Hague District Court)',                'NL', 'trial',     'manual', 'plan-2-seed'),
    ('de-bverfg',              'Bundesverfassungsgericht (Federal Constitutional Court)',      'DE', 'supreme',   'manual', 'plan-2-seed'),
    ('us-scotus',              'Supreme Court of the United States',                           'US', 'supreme',   'manual', 'plan-2-seed'),
    ('icj-court',              'International Court of Justice',                               'ICJ', 'tribunal', 'manual', 'plan-2-seed'),
    ('iacthr-court',           'Inter-American Court of Human Rights',                         'IACTHR', 'tribunal', 'manual', 'plan-2-seed')
ON CONFLICT (id) DO NOTHING;

INSERT INTO vocabulary_claim_type (code, name, description, source, source_version) VALUES
    ('human_rights',     'Human rights',           'Claims grounded in domestic or international human-rights instruments',                  'manual', 'plan-2-seed'),
    ('constitutional',   'Constitutional',         'Claims grounded in national constitutional rights',                                       'manual', 'plan-2-seed'),
    ('tort',             'Tort / civil liability', 'Claims grounded in tort law (negligence, nuisance, public-trust, etc.)',                  'manual', 'plan-2-seed'),
    ('public_trust',     'Public trust doctrine',  'Claims grounded in the public-trust doctrine',                                            'manual', 'plan-2-seed'),
    ('regulatory_challenge', 'Regulatory challenge', 'Challenges to government action, inaction, or regulation under administrative law',     'manual', 'plan-2-seed'),
    ('corporate_accountability', 'Corporate accountability', 'Claims targeting corporate emissions, disclosure, or greenwashing',             'manual', 'plan-2-seed'),
    ('environmental_assessment', 'Environmental assessment', 'Procedural challenges to project approvals (NEPA / EIA / similar)',             'manual', 'plan-2-seed'),
    ('access_to_justice', 'Access to justice',     'Procedural cases about standing, intervention, or class-action access',                   'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_status (code, name, source, source_version) VALUES
    ('filed',     'Filed',     'manual', 'plan-2-seed'),
    ('pending',   'Pending',   'manual', 'plan-2-seed'),
    ('decided',   'Decided',   'manual', 'plan-2-seed'),
    ('settled',   'Settled',   'manual', 'plan-2-seed'),
    ('dismissed', 'Dismissed', 'manual', 'plan-2-seed'),
    ('withdrawn', 'Withdrawn', 'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_outcome (code, name, source, source_version) VALUES
    ('plaintiff_won',       'Plaintiff won',       'manual', 'plan-2-seed'),
    ('defendant_won',       'Defendant won',       'manual', 'plan-2-seed'),
    ('mixed',               'Mixed',               'manual', 'plan-2-seed'),
    ('settled_favorable',   'Settled favorably',   'manual', 'plan-2-seed'),
    ('settled_unfavorable', 'Settled unfavorably', 'manual', 'plan-2-seed'),
    ('na',                  'Not applicable',      'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;

INSERT INTO vocabulary_document_category (code, name, source, source_version) VALUES
    ('opinion',       'Opinion',       'manual', 'plan-2-seed'),
    ('order',         'Order',         'manual', 'plan-2-seed'),
    ('complaint',     'Complaint',     'manual', 'plan-2-seed'),
    ('brief',         'Brief',         'manual', 'plan-2-seed'),
    ('agency_record', 'Agency record', 'manual', 'plan-2-seed'),
    ('settlement',    'Settlement',    'manual', 'plan-2-seed'),
    ('judgment',      'Judgment',      'manual', 'plan-2-seed'),
    ('dissent',       'Dissent',       'manual', 'plan-2-seed')
ON CONFLICT (code) DO NOTHING;
